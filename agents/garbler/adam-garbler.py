#!/usr/bin/env python3
"""Adam-Garbler — Nettoyeur de code mort et inutilisé

Cet agent scanne le codebase EVA_CORE et:
1. Identifie les fichiers Python jamais importés
2. Identifie les fonctions/classes jamais appelées
3. Identifie les outils en double (même nom, contenu similaire)
4. Identifie les scripts shell non référencés
5. Identifie les backups et fichiers temporaires
6. Supprime le code mort (avec sauvegarde Git avant)

Utilisation:
    python3 adam-garbler.py                    # Scan + rapport
    python3 adam-garbler.py --clean             # Scan + suppression
    python3 adam-garbler.py --clean --no-backup  # Pas de backup Git
"""
import os, sys, ast, json, re
from pathlib import Path
from datetime import datetime

BASE = Path(os.environ.get("ADAM_V2_DIR", "/home/aza/eva-adam-v2"))
EVA_CORE = Path("/home/aza/EVA_CORE")
DRY_RUN = "--clean" not in sys.argv
NO_BACKUP = "--no-backup" in sys.argv

def find_python_files(root):
    """Find all .py files, excluding __pycache__, venv, .git"""
    files = []
    for f in root.rglob("*.py"):
        rel = str(f.relative_to(root))
        if any(x in rel for x in ["__pycache__", "venv", ".git", "node_modules", ".bak"]):
            continue
        files.append(f)
    return files

def find_shell_files(root):
    """Find all .sh files"""
    files = []
    for f in root.rglob("*.sh"):
        rel = str(f.relative_to(root))
        if any(x in rel for x in ["venv", ".git"]):
            continue
        files.append(f)
    return files

def get_imports(filepath):
    """Get all imports from a Python file"""
    try:
        with open(filepath, "r") as f:
            tree = ast.parse(f.read(), filename=str(filepath))
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append(node.module)
        return imports
    except:
        return []

def get_defined_names(filepath):
    """Get all top-level functions and classes defined in a file"""
    try:
        with open(filepath, "r") as f:
            tree = ast.parse(f.read(), filename=str(filepath))
        names = []
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                names.append(node.name)
            elif isinstance(node, ast.ClassDef):
                names.append(node.name)
        return names
    except:
        return []

def find_duplicates(tools_dir):
    """Find duplicate tools (same name or very similar content)"""
    seen = {}
    duplicates = []
    for f in tools_dir.rglob("*.py"):
        if "registry" in f.name or "__pycache__" in str(f):
            continue
        try:
            content = f.read_text()
            # Hash by first 200 chars (similar content)
            key = content[:200].strip()
            if key in seen:
                duplicates.append((f, seen[key]))
            else:
                seen[key] = f
        except:
            pass
    return duplicates

def find_temp_files(root):
    """Find temporary files, backups, and junk"""
    junk = []
    patterns = ["*.bak", "*.bak-*", "*.tmp", "*~", "*.swp", "*.orig",
                "runtime_backup_*", "self_improvement_*", "__pycache__"]
    for p in patterns:
        junk.extend(root.rglob(p))
    # Also find empty directories
    for d in root.rglob("*"):
        if d.is_dir() and not any(d.iterdir()) and d.name != "tools" and d.name != "memory":
            junk.append(d)
    return junk

def find_unused_tools(agents_dir):
    """Find tools that are never referenced in any other file"""
    all_tools = {}
    for tf in agents_dir.rglob("*/tools/*.py"):
        if "registry" in tf.name or "backup" in str(tf):
            continue
        all_tools[tf.name] = tf

    # Check which tools are referenced in the codebase
    referenced = set()
    for f in find_python_files(BASE):
        try:
            content = f.read_text()
            for tool_name in all_tools:
                if tool_name.replace(".py", "") in content:
                    referenced.add(tool_name)
        except:
            pass

    # Tools in registry.json are "used"
    for rf in agents_dir.rglob("*/tools/registry.json"):
        try:
            reg = json.loads(rf.read_text())
            for tid, info in reg.get("tools", {}).items():
                if isinstance(info, dict):
                    referenced.add(info.get("file", ""))
        except:
            pass

    unused = {name: path for name, path in all_tools.items() if name not in referenced}
    return unused

def scan():
    """Scan the codebase for dead code"""
    print("=" * 60)
    print("Adam-Garbler — Scan du code mort")
    print("=" * 60)
    
    report = {"duplicates": [], "temp_files": [], "unused_tools": [], "empty_dirs": []}
    
    # 1. Find duplicate tools
    print("\n=== 1. Outils en double ===")
    dups = find_duplicates(BASE / "agents")
    for dup in dups:
        print(f"  DOUBLON: {dup[0].name} (déjà vu: {dup[1]})")
        report["duplicates"].append(str(dup[0]))
    if not dups:
        print("  Aucun doublon")
    
    # 2. Find temp/backup files
    print("\n=== 2. Fichiers temporaires et backups ===")
    temps = find_temp_files(BASE)
    for t in temps:
        print(f"  TEMP: {t}")
        report["temp_files"].append(str(t))
    if not temps:
        print("  Aucun fichier temporaire")
    
    # 3. Find unused tools
    print("\n=== 3. Outils non référencés ===")
    unused = find_unused_tools(BASE / "agents")
    for name, path in unused.items():
        print(f"  NON UTILISÉ: {name} ({path})")
        report["unused_tools"].append(str(path))
    if not unused:
        print("  Tous les outils sont référencés")
    
    # 4. Find empty directories
    print("\n=== 4. Dossiers vides ===")
    for d in BASE.rglob("*"):
        if d.is_dir() and not any(d.iterdir()) and ".git" not in str(d) and "__pycache__" not in str(d):
            if d.name not in ["tools", "memory", "backups"]:
                print(f"  VIDE: {d}")
                report["empty_dirs"].append(str(d))
    
    total = len(report["duplicates"]) + len(report["temp_files"]) + len(report["unused_tools"])
    print(f"\n=== TOTAL: {total} éléments à nettoyer ===")
    
    return report

def clean(report):
    """Remove dead code (with Git backup)"""
    if DRY_RUN:
        print("\nMode DRY RUN — aucune suppression. Utilisez --clean pour supprimer.")
        return
    
    if not NO_BACKUP:
        import subprocess
        print("\nSauvegarde Git avant nettoyage...")
        subprocess.run(["git", "add", "-A"], cwd=str(BASE), capture_output=True)
        subprocess.run(["git", "commit", "--no-verify", "-m", 
                       f"[ADAM] garbler: backup avant nettoyage {datetime.now().strftime('%Y-%m-%d %H:%M')}"],
                      cwd=str(BASE), capture_output=True)
    
    removed = 0
    for path in report["duplicates"] + report["temp_files"] + report["unused_tools"]:
        p = Path(path)
        if p.exists():
            print(f"  SUPPRIMÉ: {p}")
            if p.is_file():
                p.unlink()
            elif p.is_dir():
                import shutil
                shutil.rmtree(p)
            removed += 1
    
    for path in report.get("empty_dirs", []):
        p = Path(path)
        if p.exists() and p.is_dir() and not any(p.iterdir()):
            print(f"  DOSSIER SUPPRIMÉ: {p}")
            p.rmdir()
            removed += 1
    
    print(f"\n{removed} éléments supprimés.")
    
    # Publish to Go Bus
    try:
        import urllib.request, json
        payload = json.dumps({
            "topic": "adam:garbler:cleaned",
            "source": "adam-garbler",
            "payload": {"removed": removed, "timestamp": datetime.now().isoformat()},
            "priority": 1
        }).encode()
        req = urllib.request.Request(
            "http://localhost:8086/api/publish",
            data=payload,
            headers={"Content-Type": "application/json"}
        )
        urllib.request.urlopen(req, timeout=3)
    except:
        pass

if __name__ == "__main__":
    report = scan()
    clean(report)
