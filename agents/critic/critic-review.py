#!/usr/bin/env python3
"""
ADAM Critic — Vrai audit qualité & auto-fix de code.

Scanne de vrais fichiers .py avec AST pour trouver:
  - unused_import  → AUTO-FIX (supprime l'import) + git add
  - syntax_error   → ALERTE (publie security:alert) + task
  - high_complexity→ TASK de refactor
  - bare_except    → AUTO-FIX (remplace par except Exception)
  - todo_fixme     → recense les TODO/FIXME dans le code

Quand des fixes sont appliqués, publie git:changes_detected pour que cicd commite.

Canaux:
  - evolution:code_review (écoute — payload avec "files": [...])
  - skill:broken, skill:created, skill:updated
"""
import sys
import os
import json
import re
import ast
import argparse
import subprocess
from datetime import datetime, timezone
from collections import defaultdict
from pathlib import Path

# ─── Config ───
ADAM_V2_DIR = os.environ.get("ADAM_V2_DIR", "/home/aza/eva-adam-v2")
LOG_DIR = os.path.join(ADAM_V2_DIR, "logs")
LOG_FILE = os.path.join(LOG_DIR, "critic-handler.log")
TASKS_DIR = os.path.join(ADAM_V2_DIR, "tasks")
FIXES_DIR = os.path.join(ADAM_V2_DIR, "fixes")
EVENT_BUS = os.path.join(ADAM_V2_DIR, "publish.py")
SKILLS_DIR = os.path.expanduser("~/.hermes/skills")
REPO_DIR = os.environ.get("ADAM_REPO_DIR", "/home/aza/test-pr-repo")

# ─── Logging ───
def log(level, msg):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    line = f"[{ts}] [{level}] {msg}"
    os.makedirs(LOG_DIR, exist_ok=True)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")
    if level == "ERROR":
        print(line, file=sys.stderr)
    else:
        print(line)

def publish(channel, payload):
    try:
        payload_str = json.dumps(payload) if isinstance(payload, dict) else str(payload)
        result = subprocess.run(
            [sys.executable, EVENT_BUS, channel, payload_str],
            capture_output=True, text=True, timeout=15
        )
        log("INFO", f"Published on {channel}: {result.stdout.strip()}")
        return True
    except Exception as e:
        log("ERROR", f"Publish failed on {channel}: {e}")
        return False

# ─── Code scanning ───
def scan_python_file(filepath):
    """Scanne un fichier Python avec AST et retourne les findings."""
    findings = []
    try:
        with open(filepath, "r") as f:
            source = f.read()
    except (FileNotFoundError, PermissionError) as e:
        log("WARN", f"Cannot read {filepath}: {e}")
        return findings

    # 1. Syntax check
    try:
        tree = ast.parse(source, filename=filepath)
    except SyntaxError as e:
        findings.append({
            "type": "syntax_error",
            "severity": "critical",
            "file": filepath,
            "line": e.lineno or 0,
            "message": f"SyntaxError: {e.msg}",
            "suggestion": "",
        })
        return findings  # Can't do AST analysis if syntax is broken

    # 2. Unused imports — AST analysis
    imported_names = {}  # name → (lineno, full_import_statement)
    used_names = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.asname or alias.name.split(".")[0]
                imported_names[name] = (node.lineno, alias.name)
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                name = alias.asname or alias.name
                imported_names[name] = (node.lineno, f"from {node.module} import {alias.name}")
        elif isinstance(node, ast.Name):
            used_names.add(node.id)
        elif isinstance(node, ast.Attribute):
            # For "os.path" we need "os"
            if isinstance(node.value, ast.Name):
                used_names.add(node.value.id)

    for name, (lineno, import_str) in imported_names.items():
        if name not in used_names and name != "*":
            findings.append({
                "type": "unused_import",
                "severity": "info",
                "file": filepath,
                "line": lineno,
                "message": f"Import '{import_str}' non utilisé — supprimer",
                "suggestion": f"Remove line {lineno}",
            })

    # 3. Bare except → except Exception
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler):
            if node.type is None:
                findings.append({
                    "type": "bare_except",
                    "severity": "warning",
                    "file": filepath,
                    "line": node.lineno,
                    "message": "Bare except — should be 'except Exception'",
                    "suggestion": "Replace 'except:' with 'except Exception:'",
                })

    # 4. High complexity — count nested branches
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            complexity = 1
            for child in ast.walk(node):
                if isinstance(child, (ast.If, ast.For, ast.While, ast.With, ast.Try,
                                     ast.BoolOp, ast.ExceptHandler)):
                    complexity += 1
            if complexity > 15:
                findings.append({
                    "type": "high_complexity",
                    "severity": "warning",
                    "file": filepath,
                    "line": node.lineno,
                    "message": f"Function '{node.name}' complexity={complexity} (threshold 15)",
                    "suggestion": "Extract into smaller functions",
                })

    # 5. TODO/FIXME
    for i, line in enumerate(source.split("\n"), 1):
        if re.search(r'\b(TODO|FIXME|HACK|XXX)\b', line, re.IGNORECASE):
            findings.append({
                "type": "todo_fixme",
                "severity": "info",
                "file": filepath,
                "line": i,
                "message": f"TODO/FIXME: {line.strip()[:100]}",
                "suggestion": "",
            })

    return findings

# ─── Auto-fix: unused imports ───
def fix_unused_import(filepath, finding):
    """Supprime un import inutilisé d'un fichier Python."""
    line_num = finding.get("line", 0)
    message = finding.get("message", "")

    match = re.search(r"Import '(\S+)'", message)
    if not match:
        return False
    import_name = match.group(1)

    try:
        with open(filepath, "r") as f:
            lines = f.readlines()
    except FileNotFoundError:
        return False

    if line_num < 1 or line_num > len(lines):
        return False

    target_line = lines[line_num - 1]
    changed = False

    # Case: "import hashlib"
    simple_name = import_name.split(".")[-1]
    if re.match(rf"^\s*import\s+{re.escape(import_name)}\s*$", target_line):
        lines.pop(line_num - 1)
        changed = True
        log("INFO", f"  Removed line {line_num}: {target_line.strip()}")
    # Case: "from X import Y"
    elif "from " in target_line and simple_name in target_line:
        after_import = target_line.split("import ", 1)[-1].strip()
        names_on_line = [n.strip().rstrip(",") for n in after_import.split(",")]
        if len(names_on_line) == 1 and names_on_line[0] == simple_name:
            lines.pop(line_num - 1)
            changed = True
            log("INFO", f"  Removed line {line_num}: {target_line.strip()}")
        elif simple_name in names_on_line:
            new_names = [n for n in names_on_line if n != simple_name]
            prefix = target_line.split("import ", 1)[0] + "import "
            lines[line_num - 1] = prefix + ", ".join(new_names) + "\n"
            changed = True
            log("INFO", f"  Modified line {line_num}: {lines[line_num-1].strip()}")

    if changed:
        os.makedirs(FIXES_DIR, exist_ok=True)
        with open(filepath, "w") as f:
            f.writelines(lines)
        log("INFO", f"  ✅ Auto-fix applied: {filepath}")
        return True
    return False

# ─── Auto-fix: bare except ───
def fix_bare_except(filepath, finding):
    """Remplace 'except:' par 'except Exception:'."""
    line_num = finding.get("line", 0)
    try:
        with open(filepath, "r") as f:
            lines = f.readlines()
    except FileNotFoundError:
        return False

    if line_num < 1 or line_num > len(lines):
        return False

    target = lines[line_num - 1]
    new_line = re.sub(r'\bexcept\s*:', 'except Exception:', target, count=1)
    if new_line != target:
        lines[line_num - 1] = new_line
        with open(filepath, "w") as f:
            f.writelines(lines)
        log("INFO", f"  ✅ Fixed bare except: {filepath}:{line_num}")
        return True
    return False

# ─── Create refactor task ───
def create_refactor_task(finding, task_type="refactor"):
    os.makedirs(TASKS_DIR, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    ftype = finding.get("type", "unknown")
    fname = f"task-{task_type}-{ftype}-{ts}.md"

    filepath = finding.get("file", "unknown")
    line = finding.get("line", 0)
    severity = finding.get("severity", "info")
    message = finding.get("message", "")
    suggestion = finding.get("suggestion", "")

    content = f"""# Task: {task_type} — {ftype}

- **Fichier:** `{filepath}:{line}`
- **Sévérité:** {severity}
- **Type:** {ftype}
- **Date:** {ts}

## Problème

{message}

## Suggestion

{suggestion or "Aucune suggestion automatique — analyse manuelle requise."}
"""
    task_file = os.path.join(TASKS_DIR, fname)
    with open(task_file, "w") as f:
        f.write(content)
    log("INFO", f"  📝 Task created: {task_file}")
    return task_file

# ─── Handler: evolution:code_review ───
def handle_code_review(payload):
    """Scanne de vrais fichiers .py et applique des fixes."""

    # Get files to scan
    files = payload.get("files", [])
    auto_fix = payload.get("auto_fix", True)

    if not files:
        # Default: scan all .py in eva-adam-v2 + scripts
        log("INFO", "No files specified — scanning default directories")
        for f in Path(ADAM_V2_DIR).glob("*.py"):
            if not f.name.startswith("__"):
                files.append(str(f))
        for f in Path("/home/aza/scripts").glob("*.py"):
            files.append(str(f))

    log("INFO", f"=== Code scan: {len(files)} files ===")

    all_findings = []
    files_with_errors = 0

    for filepath in files:
        if not os.path.isfile(filepath):
            continue
        findings = scan_python_file(filepath)
        all_findings.extend(findings)
        if any(f["severity"] == "critical" for f in findings):
            files_with_errors += 1

    log("INFO", f"  Total findings: {len(all_findings)}")
    log("INFO", f"  Files with errors: {files_with_errors}")

    stats = defaultdict(int)
    fixes_applied = 0
    tasks_created = 0
    alerts_sent = 0
    fixed_files = set()

    for finding in all_findings:
        ftype = finding.get("type", "unknown")
        severity = finding.get("severity", "info")
        filepath = finding.get("file", "")
        stats[ftype] += 1

        if ftype == "unused_import" and auto_fix:
            if fix_unused_import(filepath, finding):
                fixes_applied += 1
                fixed_files.add(filepath)

        elif ftype == "bare_except" and auto_fix:
            if fix_bare_except(filepath, finding):
                fixes_applied += 1
                fixed_files.add(filepath)

        elif ftype == "syntax_error" or severity == "critical":
            log("ERROR", f"🚨 CRITICAL: {filepath}:{finding.get('line',0)} — {finding.get('message','')}")
            create_refactor_task(finding, task_type="critical")
            tasks_created += 1
            publish("security:alert", {
                "agent": "adam-critic",
                "type": "syntax_error",
                "file": filepath,
                "line": finding.get("line", 0),
                "message": finding.get("message", ""),
                "severity": "critical",
            })
            alerts_sent += 1

        elif ftype in ("high_complexity", "factorization"):
            create_refactor_task(finding, task_type="refactor")
            tasks_created += 1

    # Bilan
    log("INFO", f"=== Scan results ===")
    log("INFO", f"  Files scanned: {len(files)}")
    log("INFO", f"  Total findings: {len(all_findings)}")
    log("INFO", f"  Fixes applied: {fixes_applied}")
    log("INFO", f"  Tasks created: {tasks_created}")
    log("INFO", f"  Alerts sent: {alerts_sent}")
    log("INFO", f"  By type: {dict(stats)}")

    # Si des fixes ont été appliqués → publier pour que cicd commite
    if fixed_files:
        log("INFO", f"  Fixed files: {list(fixed_files)}")
        publish("git:changes_detected", {
            "repo": REPO_DIR,
            "branch": "Dev",
            "files": list(fixed_files),
            "source": "adam-critic",
            "msg": f"auto-fix: {fixes_applied} fixes ({', '.join(stats.keys())})",
            "auto_commit": True,
        }, )

    # Publier le bilan
    publish("wiki:update", {
        "agent": "adam-critic",
        "type": "code_review_processed",
        "files_scanned": len(files),
        "total_findings": len(all_findings),
        "fixes_applied": fixes_applied,
        "tasks_created": tasks_created,
        "alerts_sent": alerts_sent,
        "stats": dict(stats),
    })

    return {
        "files_scanned": len(files),
        "total_findings": len(all_findings),
        "fixes_applied": fixes_applied,
        "tasks_created": tasks_created,
        "alerts_sent": alerts_sent,
    }

# ─── Handler: skill events ───
def handle_skill_event(channel, payload):
    skill_name = payload.get("skill_name", payload.get("skill", ""))
    log("INFO", f"Skill event: {channel} — skill={skill_name}")
    return True

# ─── Main handler ───
def handle_event(channel, payload_str):
    try:
        payload = json.loads(payload_str) if payload_str else {}
    except json.JSONDecodeError:
        payload = {}

    log("INFO", f"Processing: channel={channel}")

    if channel == "evolution:code_review":
        return handle_code_review(payload)
    elif channel in ("skill:broken", "skill:created", "skill:updated"):
        return handle_skill_event(channel, payload)
    else:
        log("WARN", f"Unhandled channel: {channel}")
        return False

# ─── CLI ───
def main():
    parser = argparse.ArgumentParser(description="ADAM Critic — Real code audit & auto-fix")
    parser.add_argument("--event", nargs=2, metavar=("CHANNEL", "PAYLOAD"),
                        help="Handler event bus: --event <channel> '<json>'")
    parser.add_argument("--scan", action="store_true",
                        help="Scan default directories now")
    args = parser.parse_args()

    if args.event:
        channel, payload = args.event
        result = handle_event(channel, payload)
        print(json.dumps(result) if isinstance(result, dict) else str(result))
    elif args.scan:
        result = handle_code_review({"auto_fix": True})
        print(json.dumps(result, indent=2))
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
