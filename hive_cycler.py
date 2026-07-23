#!/usr/bin/env python3
"""
Adam Hive Cycler — Vrai monitoring système + déclencheur de travail réel.

Cycle de 3 minutes:
  0:00  Vrai monitoring système → alertes seulement si seuils dépassés
        (disk >85%, RAM >90%, GPU >95°C, load >4, services down)
  0:30  Scan de code → déclenche adam-critic sur les vrais .py
  1:00  Check git status → déclenche adam-cicd si changements non commités
  1:30  Health check services (event_daemon, self_heal, file_watcher, viz)
  2:00  OSINT / Research trigger → déclenche adam-researcher (1x/heure)
  2:30  Finance snapshot → déclenche adam-treasurer (1x/15min)

Usage:
  python3 hive_cycler.py              # foreground
  python3 hive_cycler.py --once       # un seul cycle
"""

import sys
import os
import time
import json
import sqlite3
import subprocess
import socket
from pathlib import Path
from datetime import datetime, timezone

ADAM_V2_DIR = Path(os.environ.get("ADAM_V2_DIR", os.path.expanduser("~/eva-adam-v2")))
DB_PATH = ADAM_V2_DIR / "event_bus.db"
LOG_DIR = ADAM_V2_DIR / "logs"
LOG_FILE = LOG_DIR / "hive_cycler.log"
REPO_DIR = Path(os.environ.get("ADAM_REPO_DIR", os.path.expanduser("~/test-pr-repo")))
SCRIPTS_DIR = Path("/home/aza/scripts")

# Seuils réels
DISK_THRESHOLD = 85    # %
RAM_THRESHOLD = 90     # %
GPU_TEMP_THRESHOLD = 85  # °C
LOAD_THRESHOLD = 4.0
GPU_VRAM_THRESHOLD = 95  # %

LOG_DIR.mkdir(parents=True, exist_ok=True)

def log(msg):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    line = f"[{ts}] [CYCLER] {msg}"
    print(line, flush=True)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")

def publish(channel, payload, source="hive_cycler", priority=5):
    """Publie un event directement dans event_bus.db."""
    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=5)
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "INSERT INTO events (channel, source, payload, status, priority, created_at) "
            "VALUES (?, ?, ?, 'pending', ?, ?)",
            (channel, source, json.dumps(payload), priority, now)
        )
        conn.commit()
        eid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.close()
        log(f"  → Event #{eid} on {channel}")
        return eid
    except Exception as e:
        log(f"  ERROR publishing {channel}: {e}")
        return None

def get_real_metrics():
    """Collecte de vraies métriques système."""
    metrics = {}
    try:
        # Disk
        result = subprocess.run(["df", "/"], capture_output=True, text=True, timeout=5)
        lines = result.stdout.strip().split("\n")
        if len(lines) >= 2:
            parts = lines[1].split()
            metrics["disk_pct"] = int(parts[4].replace("%", ""))

        # RAM
        with open("/proc/meminfo") as f:
            meminfo = {}
            for line in f:
                parts = line.split(":")
                if len(parts) == 2:
                    meminfo[parts[0].strip()] = int(parts[1].strip().split()[0])
        total = meminfo.get("MemTotal", 1)
        avail = meminfo.get("MemAvailable", 0)
        metrics["ram_pct"] = round((1 - avail / total) * 100, 1)
        metrics["ram_total_gb"] = round(total / 1024 / 1024, 1)

        # CPU load
        with open("/proc/loadavg") as f:
            metrics["load"] = float(f.read().split()[0])

        # GPU
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=index,temperature.gpu,utilization.gpu,memory.used,memory.total",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=5
            )
            gpus = []
            for line in result.stdout.strip().split("\n"):
                if line:
                    parts = [p.strip() for p in line.split(",")]
                    if len(parts) >= 5:
                        gpus.append({
                            "id": int(parts[0]),
                            "temp": int(parts[1]),
                            "util": int(parts[2]),
                            "vram_used": int(parts[3]),
                            "vram_total": int(parts[4]),
                        })
            metrics["gpus"] = gpus
        except Exception:
            metrics["gpus"] = []

        # Uptime
        with open("/proc/uptime") as f:
            metrics["uptime_seconds"] = int(float(f.read().split()[0]))

        # Hostname
        metrics["hostname"] = socket.gethostname()

    except Exception as e:
        log(f"  ERROR collecting metrics: {e}")

    return metrics

def check_services():
    """Vérifie si les services critiques tournent."""
    services = {
        "event_daemon": "event_daemon.py",
        "self_heal": "self_heal.py",
        "file_watcher": "file_watcher.py",
        "viz_server": "server.py",
    }
    results = {}
    for name, pattern in services.items():
        try:
            result = subprocess.run(
                ["pgrep", "-f", pattern],
                capture_output=True, timeout=5
            )
            results[name] = {
                "running": result.returncode == 0,
                "pids": result.stdout.strip().split("\n") if result.stdout.strip() else []
            }
        except Exception:
            results[name] = {"running": False, "pids": []}
    return results

def get_uncommitted_changes(repo_dir):
    """Détecte les changements Git non commités."""
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True, text=True, timeout=10,
            cwd=str(repo_dir)
        )
        if result.returncode != 0:
            return []
        changes = [line.strip() for line in result.stdout.strip().split("\n") if line.strip()]
        return changes
    except Exception:
        return []

def find_python_files_to_scan():
    """Trouve les fichiers .py à scanner pour le critic."""
    py_files = []
    # Scan eva-adam-v2
    for f in ADAM_V2_DIR.glob("*.py"):
        if f.name.startswith("__"):
            continue
        py_files.append(str(f))
    # Scan scripts
    if SCRIPTS_DIR.exists():
        for f in SCRIPTS_DIR.glob("*.py"):
            py_files.append(str(f))
    return py_files

# ─── Phase 1: Vrai monitoring ───
def phase_monitoring(metrics):
    """Publie des alertes seulement si les seuils sont dépassés."""
    log("  Phase 1: Monitoring système")

    # Disk
    disk_pct = metrics.get("disk_pct", 0)
    if disk_pct > DISK_THRESHOLD:
        publish("hardware:disk_alert", {
            "disk": "/",
            "usage_pct": disk_pct,
            "threshold": DISK_THRESHOLD,
            "hostname": metrics.get("hostname", "?"),
            "severity": "critical" if disk_pct > 95 else "warning",
            "msg": f"Disk at {disk_pct}% (threshold {DISK_THRESHOLD}%)"
        })

    # RAM
    ram_pct = metrics.get("ram_pct", 0)
    if ram_pct > RAM_THRESHOLD:
        publish("hardware:ram_alert", {
            "ram_pct": ram_pct,
            "ram_total_gb": metrics.get("ram_total_gb", 0),
            "threshold": RAM_THRESHOLD,
            "severity": "critical" if ram_pct > 97 else "warning",
            "msg": f"RAM at {ram_pct}% (threshold {RAM_THRESHOLD}%)"
        })

    # GPU
    for gpu in metrics.get("gpus", []):
        if gpu["temp"] > GPU_TEMP_THRESHOLD:
            publish("hardware:gpu_alert", {
                "gpu_id": gpu["id"],
                "temp": gpu["temp"],
                "threshold": GPU_TEMP_THRESHOLD,
                "severity": "critical" if gpu["temp"] > 90 else "warning",
                "msg": f"GPU {gpu['id']} temp {gpu['temp']}°C"
            })
        vram_pct = round(gpu["vram_used"] / max(gpu["vram_total"], 1) * 100, 1)
        if vram_pct > GPU_VRAM_THRESHOLD:
            publish("hardware:gpu_alert", {
                "gpu_id": gpu["id"],
                "vram_used": gpu["vram_used"],
                "vram_total": gpu["vram_total"],
                "vram_pct": vram_pct,
                "severity": "warning",
                "msg": f"GPU {gpu['id']} VRAM {vram_pct}%"
            })

    # Load
    load = metrics.get("load", 0)
    if load > LOAD_THRESHOLD:
        publish("monitor:alert", {
            "type": "high_load",
            "load": load,
            "threshold": LOAD_THRESHOLD,
            "severity": "warning",
            "msg": f"Load average {load} (threshold {LOAD_THRESHOLD})"
        })

    log(f"  Disk: {disk_pct}% | RAM: {ram_pct}% | Load: {metrics.get('load', '?')} | GPUs: {len(metrics.get('gpus', []))}")

# ─── Phase 2: Scan de code → critic ───
def phase_code_scan():
    """Déclenche adam-critic sur les vrais fichiers .py."""
    log("  Phase 2: Scan de code → adam-critic")
    py_files = find_python_files_to_scan()
    if not py_files:
        log("  Aucun fichier .py à scanner")
        return

    publish("evolution:code_review", {
        "files": py_files,
        "scan_type": "full",
        "auto_fix": True,
        "source": "hive_cycler",
        "msg": f"Scan de {len(py_files)} fichiers .py"
    })

# ─── Phase 3: Git status → cicd ───
def phase_git_check():
    """Détecte les changements non commités → déclenche cicd."""
    log("  Phase 3: Git status check")
    changes = get_uncommitted_changes(REPO_DIR)
    if changes:
        log(f"  {len(changes)} changement(s) non commité(s) détecté(s)")
        publish("git:changes_detected", {
            "repo": str(REPO_DIR),
            "branch": "Dev",
            "files": changes[:20],
            "count": len(changes),
            "msg": f"{len(changes)} uncommitted changes"
        }, priority=3)
    else:
        log("  Git clean, rien à committer")

# ─── Phase 4: Health check services ───
def phase_health_check():
    """Vérifie les services critiques."""
    log("  Phase 4: Health check services")
    services = check_services()
    down_services = [name for name, info in services.items() if not info["running"]]
    if down_services:
        log(f"  ⚠ Services down: {', '.join(down_services)}")
        publish("service:down", {
            "services": down_services,
            "hostname": socket.gethostname(),
            "severity": "critical",
            "msg": f"Services down: {', '.join(down_services)}"
        }, priority=2)
    else:
        log("  Tous les services sont UP")

# ─── Phase 5: Research trigger (1x/heure) ───
def phase_research():
    """Déclenche adam-researcher (limité à 1x/heure)."""
    global _last_research
    now = time.time()
    if hasattr(_last_research, '__call__') or _last_research == 0 or (now - _last_research) > 3600:
        log("  Phase 5: Research trigger → adam-researcher")
        publish("research:trigger", {
            "scan_type": "pubmed",
            "topics": ["mRNA", "CRISPR", "AI drug discovery", "biotech patent"],
            "max_results": 10,
            "source": "hive_cycler",
            "msg": "Periodic research scan"
        }, priority=4)
        _last_research = now
    else:
        remaining = 3600 - (now - _last_research)
        log(f"  Research skip (next in {int(remaining/60)}min)")

_last_research = 0

# ─── Phase 6: Finance snapshot (1x/15min) ───
def phase_finance():
    """Déclenche adam-treasurer (limité à 1x/15min)."""
    global _last_finance
    now = time.time()
    if _last_finance == 0 or (now - _last_finance) > 900:
        log("  Phase 6: Finance snapshot → adam-treasurer")
        publish("finance:report", {
            "report_type": "snapshot",
            "source": "hive_cycler",
            "msg": "Periodic finance snapshot"
        }, priority=4)
        _last_finance = now
    else:
        remaining = 900 - (now - _last_finance)
        log(f"  Finance skip (next in {int(remaining/60)}min)")

_last_finance = 0

# ─── Main cycle ───
PHASES = [
    (0,   phase_monitoring),
    (15,  phase_code_scan),
    (45,  phase_git_check),
    (60,  phase_health_check),
    (90,  phase_research),
    (120, phase_finance),
]

CYCLE_DURATION = 180  # 3 minutes

def run_cycle(once=False):
    log(f"🐝 Démarrage cycle (once={once})")

    cycle_num = 0
    while True:
        cycle_num += 1
        log(f"📋 Cycle #{cycle_num} — collecte métriques...")

        for delay, phase_fn in PHASES:
            if delay > 0:
                time.sleep(delay)
            try:
                if phase_fn == phase_monitoring:
                    metrics = get_real_metrics()
                    phase_fn(metrics)
                else:
                    phase_fn()
            except Exception as e:
                log(f"  ERROR in phase {phase_fn.__name__}: {e}")

        log(f"✅ Cycle #{cycle_num} terminé")

        if once:
            break

        remaining = CYCLE_DURATION - sum(d for d, _ in PHASES)
        if remaining > 0:
            log(f"⏳ Prochain cycle dans {remaining}s...")
            time.sleep(remaining)

if __name__ == "__main__":
    once = "--once" in sys.argv
    try:
        run_cycle(once=once)
    except KeyboardInterrupt:
        log("🛑 Arrêt du cycler (KeyboardInterrupt)")
        sys.exit(0)
    except Exception as e:
        log(f"💥 FATAL: {e}")
        sys.exit(1)
