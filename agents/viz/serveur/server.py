#!/usr/bin/env python3
"""Adam-Viz V4 — Dashboard ADAM via Go Bus API (HTTP).

Version locale (non-Docker) — utilise le Go Event Bus (port 8086) comme
source de données au lieu de SQLite direct. Adaptée depuis la version
docker/agents/viz/server.py.

Garde les fonctionnalités spécifiques au host :
  - Rapports OSINT (listing + download + trigger)
  - Handler logs par agent
  - Métriques système locales (GPU, RAM, disque)

Plus de dépendance SQLite directe — tout passe par l'API HTTP du Go Bus.
"""

import json
import os
import sys
import time
import threading
import subprocess
import urllib.request
import urllib.error
import urllib.parse
from pathlib import Path
from datetime import datetime, timezone, timedelta
from collections import deque
from flask import Flask, render_template, jsonify, request, send_file
from flask_sock import Sock

app = Flask(__name__)
sock = Sock(app)

# ── Config ─────────────────────────────────────────────────────────────────
BUS_URL = os.environ.get("BUS_URL", "http://localhost:8086")
ADAM_V2_DIR = Path(os.environ.get("ADAM_V2_DIR", os.path.expanduser("~/eva-adam-v2")))
LOG_DIR = ADAM_V2_DIR / "logs"
OSINT_REPORT_DIR = ADAM_V2_DIR / "osint_reports"

# Les 11 agents ADAM v2
AGENTS_META = {
    "adam-praetor":    {"emoji": "🛡️", "color": "#ff2244", "role": "Surveillance système"},
    "adam-sentinel":   {"emoji": "📡", "color": "#00ddff", "role": "Veille technologique"},
    "adam-critic":     {"emoji": "🔍", "color": "#ffdd00", "role": "Audit qualité"},
    "adam-cicd":       {"emoji": "🚀", "color": "#ffffff", "role": "CI/CD + git"},
    "adam-backup":     {"emoji": "💾", "color": "#2244aa", "role": "Sauvegarde"},
    "adam-deploy":     {"emoji": "📦", "color": "#00ff88", "role": "Déploiement"},
    "adam-monitor":    {"emoji": "📊", "color": "#ff8800", "role": "Monitoring hardware"},
    "adam-doctor":     {"emoji": "👨‍⚕️", "color": "#aa66ff", "role": "Post-redémarrage"},
    "adam-blue":       {"emoji": "🔵", "color": "#4488ff", "role": "Sécurité Blue Team"},
    "adam-red":        {"emoji": "🔴", "color": "#ff4444", "role": "OSINT / Red Team"},
    "adam-viz-checker":{"emoji": "👁️", "color": "#88ffaa", "role": "Vérification dashboards"},
}

# Mapping agent → handler log file
HANDLER_LOGS = {
    "adam-praetor":    "praetor-handler.log",
    "adam-blue":       "blue-handler.log",
    "adam-cicd":       "cicd-handler.log",
    "adam-critic":     "critic-handler.log",
    "adam-monitor":    "monitor-handler.log",
    "adam-deploy":     "deploy-handler.log",
    "adam-backup":     "backup-handler.log",
    "adam-sentinel":   "sentinel-handler.log",
    "adam-doctor":     "doctor-handler.log",
    "adam-viz-checker":"viz-checker.log",
    "adam-red":        "red-handler.log",
}

# ── État global ─────────────────────────────────────────────────────────────
ws_clients = set()
start_time = time.time()
event_buffer = deque(maxlen=100)  # cache des derniers events pour le feed temps réel

# ── Go Bus HTTP Client ─────────────────────────────────────────────────────
def bus_get(path):
    """GET sur le Go Bus, retourne le JSON décodé ou None."""
    try:
        req = urllib.request.Request(f"{BUS_URL}{path}")
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        print(f"[BUS GET ERROR] {path}: {e}", file=sys.stderr)
        return None

def bus_publish(topic, source, payload, priority=0):
    """POST un événement sur le Go Bus via /api/publish."""
    data = json.dumps({
        "topic": topic,
        "source": source,
        "payload": payload,
        "priority": priority,
    }).encode()
    try:
        req = urllib.request.Request(
            f"{BUS_URL}/api/publish",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        print(f"[BUS PUBLISH ERROR] {e}", file=sys.stderr)
        return None

def get_bus_events(topic=None, limit=50):
    """Récupère les événements depuis le Go Bus (/api/query)."""
    q = f"/api/query?limit={limit}"
    if topic:
        q += f"&topic={urllib.parse.quote(topic)}"
    data = bus_get(q)
    if data and "events" in data:
        return data["events"]
    return []

def get_bus_stats():
    """Statistiques globales du Go Bus (/api/stats)."""
    data = bus_get("/api/stats")
    if isinstance(data, dict):
        return data
    return {}

# ── Agents / Events depuis le bus ──────────────────────────────────────────
def get_agents():
    """Construit la liste des agents à partir des events récents du bus."""
    events = get_bus_events(limit=200)
    agents = []
    seen = set()
    # Pré-remplir avec tous les agents connus (même si pas d'event récent)
    for aid, meta in AGENTS_META.items():
        if aid not in seen:
            seen.add(aid)
            agents.append({
                "id": aid,
                "display_name": aid.replace("adam-", "").title(),
                "emoji": meta["emoji"],
                "color": meta["color"],
                "role": meta["role"],
                "status": "idle",
                "last_status": "",
                "last_error": "",
                "last_run_at": "",
                "heartbeat_at": "",
                "is_stale": True,
                "channels": [],
                "total_runs": 0,
                "successful_runs": 0,
            })
    # Enrichir avec les events récents
    for e in events:
        source = e.get("source", "unknown")
        if source in seen and source in AGENTS_META:
            # Mettre à jour l'agent existant
            for a in agents:
                if a["id"] == source:
                    a["status"] = "running" if e.get("status") == "done" else "idle"
                    a["last_status"] = e.get("status", "")
                    a["last_run_at"] = e.get("created_at", "")
                    a["heartbeat_at"] = e.get("created_at", "")
                    a["is_stale"] = False
                    a["total_runs"] += 1
                    if e.get("status") == "done":
                        a["successful_runs"] += 1
                    ch = e.get("topic", "")
                    if ch and ch not in a["channels"]:
                        a["channels"].append(ch)
                    break
        elif source not in seen:
            seen.add(source)
            meta = AGENTS_META.get(source, {"emoji": "🤖", "color": "#888", "role": "Inconnu"})
            agents.append({
                "id": source,
                "display_name": source.replace("adam-", "").title(),
                "emoji": meta["emoji"],
                "color": meta["color"],
                "role": meta["role"],
                "status": "running" if e.get("status") == "done" else "idle",
                "last_status": e.get("status", ""),
                "last_error": e.get("error", ""),
                "last_run_at": e.get("created_at", ""),
                "heartbeat_at": e.get("created_at", ""),
                "is_stale": False,
                "channels": [e.get("topic", "")],
                "total_runs": 1,
                "successful_runs": 1 if e.get("status") == "done" else 0,
            })
    return agents

def get_recent_events(limit=50):
    """Récupère les derniers events du Go Bus."""
    events = get_bus_events(limit=limit)
    result = []
    for e in events:
        result.append({
            "id": e.get("id", ""),
            "channel": e.get("topic", ""),
            "source": e.get("source", ""),
            "status": e.get("status", "done"),
            "created_at": e.get("created_at", ""),
            "processed_at": e.get("created_at", ""),
            "priority": e.get("priority", 0),
            "latency_ms": e.get("latency_ms"),
        })
    return result

def get_handler_logs(agent_id, lines=50):
    """Lit les dernières lignes du log d'un handler."""
    log_file = HANDLER_LOGS.get(agent_id)
    if not log_file:
        return []
    path = LOG_DIR / log_file
    if not path.exists():
        return []
    try:
        with open(path, "r", errors="replace") as f:
            all_lines = f.readlines()
        return [l.strip() for l in all_lines[-lines:] if l.strip()]
    except Exception:
        return []

def get_daemon_status():
    """Vérifie si les daemons tournent (via ps aux)."""
    daemons = {}
    try:
        result = subprocess.run(["ps", "aux"], capture_output=True, text=True, timeout=5)
        ps_output = result.stdout
        daemons["event_daemon"] = "event_daemon.py" in ps_output
        daemons["file_watcher"] = "file_watcher.py" in ps_output
        daemons["self_heal"] = "self_heal.py" in ps_output
    except Exception:
        daemons = {"event_daemon": False, "file_watcher": False, "self_heal": False}
    return daemons

def get_system_metrics():
    """Métriques système rapides (CPU load, RAM, disk, GPU)."""
    metrics = {}
    try:
        # CPU load
        with open("/proc/loadavg") as f:
            metrics["load_avg"] = f.read().split()[:3]

        # RAM
        with open("/proc/meminfo") as f:
            meminfo = {}
            for line in f:
                parts = line.split(":")
                if len(parts) == 2:
                    meminfo[parts[0].strip()] = int(parts[1].strip().split()[0])
        total = meminfo.get("MemTotal", 0)
        avail = meminfo.get("MemAvailable", 0)
        metrics["ram_total_gb"] = round(total / 1024 / 1024, 1)
        metrics["ram_used_gb"] = round((total - avail) / 1024 / 1024, 1)
        metrics["ram_pct"] = round((1 - avail / total) * 100, 1) if total > 0 else 0

        # Disk
        result = subprocess.run(["df", "/"], capture_output=True, text=True, timeout=5)
        lines = result.stdout.strip().split("\n")
        if len(lines) >= 2:
            parts = lines[1].split()
            metrics["disk_pct"] = int(parts[4].replace("%", ""))
            metrics["disk_used"] = parts[2]
            metrics["disk_total"] = parts[1]

        # GPU (nvidia-smi)
        try:
            result = subprocess.run(
                ["nvidia-smi",
                 "--query-gpu=index,name,temperature.gpu,utilization.gpu,memory.used,memory.total",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=5,
            )
            gpus = []
            for line in result.stdout.strip().split("\n"):
                if line:
                    parts = [p.strip() for p in line.split(",")]
                    if len(parts) >= 6:
                        gpus.append({
                            "id": parts[0],
                            "name": parts[1],
                            "temp": int(parts[2]),
                            "util": int(parts[3]),
                            "vram_used": int(parts[4]),
                            "vram_total": int(parts[5]),
                        })
            metrics["gpus"] = gpus
        except Exception:
            metrics["gpus"] = []
    except Exception:
        pass
    return metrics

# ── WebSocket broadcast ────────────────────────────────────────────────────
def broadcast(data):
    """Diffuse un message à tous les clients WebSocket connectés."""
    msg = json.dumps(data)
    dead = set()
    for client in list(ws_clients):
        try:
            client.send(msg)
        except Exception:
            dead.add(client)
    ws_clients.difference_update(dead)

def monitoring_loop():
    """Boucle principale : poll le Go Bus toutes les 2s, broadcast les updates."""
    tick = 0
    while True:
        try:
            agents = get_agents()
            events = get_recent_events(20)
            bus_stats = get_bus_stats()
            daemons = get_daemon_status()
            data = {
                "type": "update",
                "tick": tick,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "agents": agents,
                "events": events,
                "bus_stats": bus_stats,
                "daemons": daemons,
                "uptime_seconds": int(time.time() - start_time),
            }
            broadcast(data)
            tick += 1
        except Exception as e:
            print(f"[ERROR] monitoring_loop: {e}", file=sys.stderr)
        time.sleep(2)

# ── Routes ─────────────────────────────────────────────────────────────────
@app.route("/hive")
def hive_page():
    """Vue 3D The Hive — visualisation temps réel des Adams."""
    return render_template("hive.html")

@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "service": "adam-viz-v4",
        "bus_url": BUS_URL,
        "agents": len(AGENTS_META),
        "clients_ws": len(ws_clients),
    })

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/agents")
def api_agents():
    return jsonify({"agents": get_agents()})

@app.route("/api/events")
def api_events():
    return jsonify({"events": get_recent_events(100)})

@app.route("/api/stats")
def api_stats():
    return jsonify(get_bus_stats())

@app.route("/api/system")
def api_system():
    return jsonify(get_system_metrics())

@app.route("/api/daemons")
def api_daemons():
    return jsonify(get_daemon_status())

@app.route("/api/handler-logs/<agent_id>")
def api_handler_logs(agent_id):
    return jsonify({"agent_id": agent_id, "logs": get_handler_logs(agent_id, 50)})

@app.route("/api/chains")
def api_chains():
    """Retourne les chaînes inter-agent récentes (events non-heartbeat)."""
    events = get_bus_events(limit=60)
    chains = []
    for e in events:
        topic = e.get("topic", "")
        if "heartbeat" not in topic:
            chains.append({
                "id": e.get("id", ""),
                "channel": topic,
                "source": e.get("source", ""),
                "status": e.get("status", "done"),
                "time": str(e.get("created_at", ""))[11:19],
                "payload": json.dumps(e.get("payload", {}))[:200],
            })
    return jsonify({"chains": chains})

# ── OSINT REPORTS ──────────────────────────────────────────────────────────
@app.route("/api/osint/reports")
def api_osint_reports():
    """Liste tous les rapports OSINT disponibles (récursif, par date)."""
    reports = []
    if OSINT_REPORT_DIR.exists():
        for f in sorted(OSINT_REPORT_DIR.rglob("*"), key=lambda x: x.stat().st_mtime, reverse=True):
            if f.is_file() and f.suffix in ('.html', '.json'):
                stat = f.stat()
                rel_path = f.relative_to(OSINT_REPORT_DIR)
                reports.append({
                    "filename": str(rel_path),
                    "path": str(f),
                    "size": stat.st_size,
                    "size_human": f"{stat.st_size / 1024:.1f} KB" if stat.st_size < 1024 * 1024 else f"{stat.st_size / 1024 / 1024:.1f} MB",
                    "modified": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                    "type": f.suffix.lstrip('.'),
                    "url": f"/api/osint/download/{rel_path}",
                })
    return jsonify({"reports": reports, "total": len(reports)})

@app.route("/api/osint/download/<path:filename>")
def api_osint_download(filename):
    """Télécharge un rapport OSINT (supporte les sous-dossiers par date)."""
    safe_name = os.path.normpath(filename)
    if safe_name.startswith("..") or safe_name.startswith("/"):
        return jsonify({"error": "Invalid path"}), 400
    filepath = OSINT_REPORT_DIR / safe_name
    if not filepath.exists():
        return jsonify({"error": "File not found"}), 404
    mimetype = "text/html" if filepath.suffix == ".html" else "application/json"
    return send_file(str(filepath), mimetype=mimetype, as_attachment=True, download_name=filepath.name)

@app.route("/api/osint/trigger", methods=["POST"])
def api_osint_trigger():
    """Déclenche une recherche OSINT en publiant un event sur le Go Bus."""
    data = request.get_json() or {}
    target = data.get("target", "").strip()
    if not target:
        return jsonify({"error": "Missing 'target' parameter"}), 400
    result = bus_publish(
        topic="osint:alert",
        source="adam-viz",
        payload={"target": target, "msg": "OSINT scan triggered from dashboard"},
        priority=1,
    )
    if result:
        return jsonify({"status": "published", "result": result, "target": target})
    return jsonify({"error": "Failed to publish to Go Bus"}), 500

# ── WebSocket ──────────────────────────────────────────────────────────────
@sock.route("/ws")
def handle_ws(conn):
    ws_clients.add(conn)
    try:
        agents = get_agents()
        events = get_recent_events(20)
        bus_stats = get_bus_stats()
        daemons = get_daemon_status()
        initial = {
            "type": "init",
            "agents": agents,
            "events": events,
            "bus_stats": bus_stats,
            "daemons": daemons,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        conn.send(json.dumps(initial))
        while True:
            msg = conn.receive()
            if msg is None:
                break
    except Exception:
        pass
    finally:
        ws_clients.discard(conn)

# ── Lancement ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    t = threading.Thread(target=monitoring_loop, daemon=True)
    t.start()

    print("╔═══════════════════════════════════════════════╗")
    print("║  🐝  Adam-Viz V4  —  Go Bus API Dashboard    ║")
    print("╠═══════════════════════════════════════════════╣")
    print(f"║  Bus: {BUS_URL}")
    print(f"║  http://0.0.0.0:8084                          ║")
    print("║  11 agents · Go Bus HTTP · WebSocket          ║")
    print("║  /api/agents /api/events /api/stats /api/system║")
    print("╚═══════════════════════════════════════════════╝")

    app.run(host="0.0.0.0", port=8084, debug=False, threaded=True)
