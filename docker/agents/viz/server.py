#!/usr/bin/env python3
"""Adam-Viz V3 — Dashboard temps réel ADAM v2.

Lit directement event_bus.db pour afficher :
- Les 11 agents et leur statut réel (idle/running/error)
- Le flux d'événements en temps réel (WebSocket)
- Les métriques du bus (events/min, taux de succès, latence)
- Les handlers et leurs logs récents
"""

import json
import os
import sys
import time
import sqlite3
import threading
import subprocess
from pathlib import Path
from datetime import datetime, timezone, timedelta
from collections import deque, defaultdict
from flask import Flask, render_template, jsonify
from flask_sock import Sock

app = Flask(__name__)
sock = Sock(app)

# ============================================================
# CONFIG
# ============================================================
ADAM_V2_DIR = Path(os.environ.get("ADAM_V2_DIR", os.path.expanduser("~/eva-adam-v2")))
DB_PATH = ADAM_V2_DIR / "event_bus.db"
LOG_DIR = ADAM_V2_DIR / "logs"
HANDLER_LOG_DIR = LOG_DIR  # handler logs like praetor-handler.log, etc.

# Les 11 agents réels d'ADAM v2
AGENTS_META = {
    "adam-praetor":    {"emoji": "🛡️", "color": "#ff2244", "role": "Surveillance système"},
    "adam-sentinel":   {"emoji": "📡", "color": "#00ddff", "role": "Veille technologique"},
    "adam-critic":     {"emoji": "🔍", "color": "#ffdd00", "role": "Audit qualité"},
    "adam-cicd":       {"emoji": "🚀", "color": "#ffffff", "color2": "#aaa", "role": "CI/CD + git"},
    "adam-backup":     {"emoji": "💾", "color": "#2244aa", "role": "Sauvegarde"},
    "adam-deploy":     {"emoji": "📦", "color": "#00ff88", "role": "Déploiement"},
    "adam-monitor":    {"emoji": "📊", "color": "#ff8800", "role": "Monitoring hardware"},
    "adam-doctor":     {"emoji": "👨‍⚕️", "color": "#aa66ff", "role": "Post-redémarrage"},
    "adam-blue":       {"emoji": "🔵", "color": "#4488ff", "role": "Sécurité Blue Team"},
    "adam-red":        {"emoji": "🔴", "color": "#ff4444", "role": "OSINT / Red Team"},
    "adam-viz-checker":{"emoji": "👁️", "color": "#88ffaa", "role": "Vérification dashboards"},
}

# Mapping canal → handler log file
HANDLER_LOGS = {
    "adam-praetor":    "praetor-handler.log",
    "adam-blue":       "blue-handler.log",
    "adam-cicd":       "cicd-handler.log",
    "adam-critic":     "critic-handler.log",
    "adam-monitor":   "monitor-handler.log",
    "adam-deploy":    "deploy-handler.log",
    "adam-backup":    "backup-handler.log",
    "adam-sentinel":  "sentinel-handler.log",
    "adam-doctor":    "doctor-handler.log",
    "adam-viz-checker":"viz-checker.log",
    "adam-red":       "red-handler.log",
}

# ============================================================
# ÉTAT GLOBAL
# ============================================================
ws_clients = set()
event_buffer = deque(maxlen=100)  # 100 derniers events pour le feed temps réel
agent_states = {}  # cache des états d'agents
stats = {
    "total_events": 0,
    "total_done": 0,
    "total_failed": 0,
    "events_per_minute": 0,
    "avg_latency_ms": 0,
    "uptime_seconds": 0,
}
start_time = time.time()
last_events_count = 0
last_check_time = time.time()

# ============================================================
# LECTURE DB
# ============================================================
def db_conn():
    """Connexion SQLite avec timeout WAL."""
    conn = sqlite3.connect(str(DB_PATH), timeout=3)
    conn.row_factory = sqlite3.Row
    return conn

def get_agents_from_db():
    """Lit les 11 agents et leur état depuis event_bus.db."""
    agents = []
    try:
        conn = db_conn()
        rows = conn.execute("SELECT * FROM agents ORDER BY agent_id").fetchall()
        for row in rows:
            aid = row["agent_id"]
            meta = AGENTS_META.get(aid, {"emoji": "🤖", "color": "#888", "role": "Inconnu"})
            
            # Subscriptions de cet agent
            subs = conn.execute(
                "SELECT channel, handler, enabled FROM subscriptions WHERE agent_id=? AND enabled=1",
                (aid,)
            ).fetchall()
            channels = [s["channel"] for s in subs]
            
            # Dernière exécution
            last_exec = conn.execute(
                "SELECT * FROM execution_log WHERE agent_id=? ORDER BY id DESC LIMIT 1",
                (aid,)
            ).fetchone()
            
            # Compter les exécutions
            exec_count = conn.execute(
                "SELECT COUNT(*), SUM(success) FROM execution_log WHERE agent_id=?",
                (aid,)
            ).fetchone()
            total_runs = exec_count[0] or 0
            successful_runs = exec_count[1] or 0
            
            # Statut
            status = row["status"] or "idle"
            last_status = row["last_status"] or ""
            last_error = row["last_error"] or ""
            heartbeat = row["heartbeat_at"] or ""
            
            # Déterminer si stale (heartbeat > 10min)
            is_stale = False
            if heartbeat:
                try:
                    hb_dt = datetime.fromisoformat(heartbeat.replace("Z", "+00:00"))
                    age = (datetime.now(timezone.utc) - hb_dt).total_seconds()
                    is_stale = age > 600
                except Exception:
                    pass
            
            agents.append({
                "id": aid,
                "display_name": row["display_name"],
                "emoji": meta["emoji"],
                "color": meta["color"],
                "role": meta["role"],
                "status": status,
                "last_status": last_status,
                "last_error": last_error,
                "heartbeat_at": heartbeat,
                "is_stale": is_stale,
                "channels": channels,
                "total_runs": total_runs,
                "successful_runs": successful_runs,
                "last_run_at": row["last_run_at"] or "",
                "pid": row["pid"],
                "config": json.loads(row["config"] or "{}"),
            })
        conn.close()
    except Exception as e:
        print(f"[ERROR] get_agents_from_db: {e}", file=sys.stderr)
    return agents

def get_recent_events(limit=50):
    """Récupère les derniers events du bus."""
    events = []
    try:
        conn = db_conn()
        rows = conn.execute(
            "SELECT id, channel, source, status, created_at, processed_at, priority "
            "FROM events ORDER BY id DESC LIMIT ?",
            (limit,)
        ).fetchall()
        for r in rows:
            latency_ms = None
            if r["processed_at"] and r["created_at"]:
                try:
                    created = datetime.fromisoformat(r["created_at"].replace("Z", "+00:00"))
                    processed = datetime.fromisoformat(r["processed_at"].replace("Z", "+00:00"))
                    latency_ms = int((processed - created).total_seconds() * 1000)
                except Exception:
                    pass
            events.append({
                "id": r["id"],
                "channel": r["channel"],
                "source": r["source"],
                "status": r["status"],
                "created_at": r["created_at"],
                "processed_at": r["processed_at"],
                "priority": r["priority"],
                "latency_ms": latency_ms,
            })
        conn.close()
    except Exception as e:
        print(f"[ERROR] get_recent_events: {e}", file=sys.stderr)
    return events

def get_bus_stats():
    """Statistiques globales du bus."""
    try:
        conn = db_conn()
        
        # Compteurs par statut
        status_counts = {}
        for row in conn.execute("SELECT status, COUNT(*) FROM events GROUP BY status"):
            status_counts[row[0]] = row[1]
        
        # Events par canal (top 10)
        channel_counts = {}
        for row in conn.execute("SELECT channel, COUNT(*) FROM events GROUP BY channel ORDER BY COUNT(*) DESC LIMIT 10"):
            channel_counts[row[0]] = row[1]
        
        # Latence moyenne (derniers 100 events traités)
        latency_rows = conn.execute(
            "SELECT created_at, processed_at FROM events "
            "WHERE status='done' AND processed_at IS NOT NULL "
            "ORDER BY id DESC LIMIT 100"
        ).fetchall()
        latencies = []
        for r in latency_rows:
            try:
                created = datetime.fromisoformat(r["created_at"].replace("Z", "+00:00"))
                processed = datetime.fromisoformat(r["processed_at"].replace("Z", "+00:00"))
                latencies.append((processed - created).total_seconds() * 1000)
            except Exception:
                pass
        avg_latency = sum(latencies) / len(latencies) if latencies else 0
        
        # Events de la dernière minute
        one_min_ago = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
        recent_count = conn.execute(
            "SELECT COUNT(*) FROM events WHERE created_at > ?", (one_min_ago,)
        ).fetchone()[0]
        
        # Events par agent (top handlers)
        agent_counts = {}
        for row in conn.execute(
            "SELECT agent_id, COUNT(*) FROM execution_log GROUP BY agent_id ORDER BY COUNT(*) DESC"
        ):
            agent_counts[row[0]] = row[1]
        
        conn.close()
        
        return {
            "total": sum(status_counts.values()),
            "pending": status_counts.get("pending", 0),
            "processing": status_counts.get("processing", 0),
            "done": status_counts.get("done", 0),
            "failed": status_counts.get("failed", 0),
            "skipped": status_counts.get("skipped", 0),
            "events_per_minute": recent_count,
            "avg_latency_ms": round(avg_latency, 1),
            "channels": channel_counts,
            "agent_runs": agent_counts,
        }
    except Exception as e:
        print(f"[ERROR] get_bus_stats: {e}", file=sys.stderr)
        return {}

def get_handler_logs(agent_id, lines=20):
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
    """Vérifie si les daemons tournent."""
    daemons = {}
    try:
        result = subprocess.run(
            ["ps", "aux"], capture_output=True, text=True, timeout=5
        )
        ps_output = result.stdout
        daemons["event_daemon"] = "event_daemon.py" in ps_output
        daemons["file_watcher"] = "file_watcher.py" in ps_output
        daemons["self_heal"] = "self_heal.py" in ps_output
    except Exception:
        daemons = {"event_daemon": False, "file_watcher": False, "self_heal": False}
    return daemons

def get_system_metrics():
    """Métriques système rapides."""
    metrics = {}
    try:
        # CPU
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
        
        # GPU
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=index,name,temperature.gpu,utilization.gpu,memory.used,memory.total",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=5
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


# ============================================================
# BROADCAST WEBSOCKET
# ============================================================
def broadcast(data):
    msg = json.dumps(data)
    dead = set()
    for client in list(ws_clients):
        try:
            client.send(msg)
        except Exception:
            dead.add(client)
    ws_clients.difference_update(dead)


def monitoring_loop():
    """Boucle principale : lit le bus toutes les 2s, broadcast les updates."""
    tick = 0
    while True:
        try:
            agents = get_agents_from_db()
            events = get_recent_events(20)
            bus_stats = get_bus_stats()
            daemons = get_daemon_status()
            
            # Calculer les events/nouveau depuis le dernier tick
            global last_events_count, last_check_time
            now = time.time()
            total_events = bus_stats.get("total", 0)
            time_delta = now - last_check_time
            if time_delta > 0:
                events_delta = total_events - last_events_count
                events_per_min = (events_delta / time_delta) * 60
                bus_stats["events_per_minute"] = round(events_per_min, 1)
            last_events_count = total_events
            last_check_time = now
            
            data = {
                "type": "update",
                "tick": tick,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "agents": agents,
                "events": events,
                "bus_stats": bus_stats,
                "daemons": daemons,
                "uptime_seconds": int(now - start_time),
            }
            broadcast(data)
            tick += 1
        except Exception as e:
            print(f"[ERROR] monitoring_loop: {e}", file=sys.stderr)
        
        time.sleep(2)


# ============================================================
# API ENDPOINTS
# ============================================================
@app.route("/hive")
def hive_page():
    """Vue 3D The Hive — visualisation temps réel des Adams."""
    return render_template("hive.html")

@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "service": "adam-viz-v3",
        "agents": len(AGENTS_META),
        "db": str(DB_PATH),
        "db_exists": DB_PATH.exists(),
        "clients_ws": len(ws_clients),
    })

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/agents")
def api_agents():
    return jsonify({"agents": get_agents_from_db()})

@app.route("/api/chains")
def api_chains():
    """Retourne les chaînes inter-agent récentes (events non-heartbeat avec follow-up)."""
    import sqlite3 as sq3
    chains = []
    try:
        conn = sq3.connect(str(DB_PATH))
        conn.row_factory = sq3.Row
        # Events récents non-heartbeat, triés par timestamp
        rows = conn.execute("""
            SELECT id, channel, source, status, created_at, payload
            FROM events
            WHERE channel NOT LIKE '%heartbeat%'
            ORDER BY id DESC
            LIMIT 60
        """).fetchall()
        for r in rows:
            chains.append({
                "id": r["id"],
                "channel": r["channel"],
                "source": r["source"],
                "status": r["status"],
                "time": r["created_at"][11:19] if r["created_at"] else "",
                "payload": r["payload"][:200] if r["payload"] else "",
            })
        conn.close()
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    return jsonify({"chains": chains})

@app.route("/api/events")
def api_events():
    return jsonify({"events": get_recent_events(100)})

@app.route("/api/stats")
def api_stats():
    return jsonify(get_bus_stats())

@app.route("/api/daemons")
def api_daemons():
    return jsonify(get_daemon_status())

@app.route("/api/system")
def api_system():
    return jsonify(get_system_metrics())

@app.route("/api/handler-logs/<agent_id>")
def api_handler_logs(agent_id):
    return jsonify({"agent_id": agent_id, "logs": get_handler_logs(agent_id, 50)})


# ============================================================
# OSINT REPORTS — Téléchargement
# ============================================================
OSINT_REPORT_DIR = ADAM_V2_DIR / "osint_reports"

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
    from flask import send_file
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
    """Déclenche une recherche OSINT en publiant un event."""
    from flask import request
    data = request.get_json() or {}
    target = data.get("target", "").strip()
    if not target:
        return jsonify({"error": "Missing 'target' parameter"}), 400
    try:
        from event_bus import EventBus
        bus = EventBus()
        eid = bus.publish("osint:alert", {"target": target, "msg": f"OSINT scan triggered from dashboard"})
        return jsonify({"status": "published", "event_id": eid, "target": target})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================================
# WEBSOCKET
# ============================================================
@sock.route("/ws")
def handle_ws(conn):
    ws_clients.add(conn)
    try:
        # Envoyer l'état initial immédiatement
        agents = get_agents_from_db()
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


# ============================================================
# LANCEMENT
# ============================================================
if __name__ == "__main__":
    # Thread de monitoring
    t = threading.Thread(target=monitoring_loop, daemon=True)
    t.start()
    
    print("╔═══════════════════════════════════════════════╗")
    print("║  🐝  Adam-Viz V3  —  Hive Dashboard Temps Réel ║")
    print("╠═══════════════════════════════════════════════╣")
    print(f"║  DB: {DB_PATH}")
    print(f"║  http://0.0.0.0:8084                          ║")
    print(f"║  11 agents · WebSocket · event_bus.db         ║")
    print("║  /api/agents /api/events /api/stats /api/system║")
    print("╚═══════════════════════════════════════════════╝")
    
    app.run(host="0.0.0.0", port=8084, debug=False, threaded=True)
