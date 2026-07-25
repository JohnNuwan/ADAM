#!/usr/bin/env python3
"""Adam-Viz V4 — Dashboard ADAM via Go Bus API (HTTP).

Utilise le Go Event Bus (port 8086) comme source de données,
plus PostgreSQL pour les stats historiques. Plus de dépendance SQLite.
"""

import json, os, sys, time, threading, subprocess, urllib.request, urllib.error
from pathlib import Path
from datetime import datetime, timezone, timedelta
from collections import deque
from flask import Flask, render_template, jsonify
from flask_sock import Sock

app = Flask(__name__)
sock = Sock(app)

# ── Config ──
BUS_URL = os.environ.get("BUS_URL", "http://go-bus:8086")
ADAM_V2_DIR = Path(os.environ.get("ADAM_V2_DIR", "/home/aza/eva-adam-v2"))
LOG_DIR = ADAM_V2_DIR / "logs"

AGENTS_META = {
    "adam-praetor":    {"emoji": "\U0001f6e1\ufe0f", "color": "#ff2244", "role": "Surveillance système"},
    "adam-sentinel":   {"emoji": "\U0001f4e1", "color": "#00ddff", "role": "Veille technologique"},
    "adam-critic":     {"emoji": "\U0001f50d", "color": "#ffdd00", "role": "Audit qualité"},
    "adam-cicd":       {"emoji": "\U0001f680", "color": "#ffffff", "role": "CI/CD + git"},
    "adam-backup":     {"emoji": "\U0001f4be", "color": "#2244aa", "role": "Sauvegarde"},
    "adam-deploy":     {"emoji": "\U0001f4e6", "color": "#00ff88", "role": "Déploiement"},
    "adam-monitor":    {"emoji": "\U0001f4ca", "color": "#ff8800", "role": "Monitoring hardware"},
    "adam-doctor":     {"emoji": "\U0001f468\u200d\u2695\ufe0f", "color": "#aa66ff", "role": "Post-redémarrage"},
    "adam-blue":       {"emoji": "\U0001f535", "color": "#4488ff", "role": "Sécurité Blue Team"},
    "adam-red":        {"emoji": "\U0001f534", "color": "#ff4444", "role": "OSINT / Red Team"},
    "adam-viz-checker":{"emoji": "\U0001f441\ufe0f", "color": "#88ffaa", "role": "Vérification dashboards"},
}

HANDLER_LOGS = {
    "adam-praetor": "praetor-handler.log", "adam-blue": "blue-handler.log",
    "adam-cicd": "cicd-handler.log", "adam-critic": "critic-handler.log",
    "adam-monitor": "monitor-handler.log", "adam-deploy": "deploy-handler.log",
    "adam-backup": "backup-handler.log", "adam-sentinel": "sentinel-handler.log",
    "adam-doctor": "doctor-handler.log", "adam-viz-checker": "viz-checker.log",
    "adam-red": "red-handler.log",
}

# ── État global ──
ws_clients = set()
start_time = time.time()

# ── Go Bus HTTP Client ──
def bus_get(path):
    try:
        req = urllib.request.Request(f"{BUS_URL}{path}")
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        print(f"[BUS GET ERROR] {path}: {e}", file=sys.stderr)
        return None

def bus_publish(topic, source, payload, priority=1):
    data = json.dumps({"topic": topic, "source": source, "payload": payload, "priority": priority}).encode()
    try:
        req = urllib.request.Request(f"{BUS_URL}/api/publish", data=data,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        print(f"[BUS PUBLISH ERROR] {e}", file=sys.stderr)
        return None

def get_bus_events(topic=None, limit=50):
    q = f"/api/query?topic=adam:packet&limit={limit}"
    if topic:
        q += f"&topic={topic}"
    data = bus_get(q)
    if data and "events" in data:
        return data["events"]
    return []

def get_bus_stats():
    data = bus_get("/api/stats")
    if isinstance(data, dict):
        return data
    return {}

# ── Agents / Events depuis le bus ──
def get_agents():
    events = get_bus_events(limit=100)
    agents = []
    seen = set()
    for e in events:
        source = e.get("source", "unknown")
        if source in seen:
            continue
        seen.add(source)
        meta = AGENTS_META.get(source, {"emoji": "\U0001f916", "color": "#888", "role": "Inconnu"})
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
            "channels": [e.get("topic", "")],
            "total_runs": 1,
            "successful_runs": 1 if e.get("status") == "done" else 0,
        })
    return agents

def get_recent_events(limit=50):
    """Interroge tous les topics du Go Bus et retourne les events recents"""
    import urllib.request
    bus = os.environ.get("BUS_URL", "http://192.168.1.5:8086")
    all_events = []
    try:
        req = urllib.request.Request(f"{bus}/api/stats")
        with urllib.request.urlopen(req, timeout=3) as resp:
            stats = json.loads(resp.read().decode())
        for key, count in stats.items():
            if key.startswith("topic:"):
                topic = key[6:]
                try:
                    q = urllib.request.Request(f"{bus}/api/query?limit=5&topic={topic}")
                    with urllib.request.urlopen(q, timeout=2) as qresp:
                        data = json.loads(qresp.read().decode())
                        if isinstance(data, list):
                            for e in data:
                                all_events.append({
                                    "id": e.get("id", ""),
                                    "channel": e.get("topic", ""),
                                    "source": e.get("source", ""),
                                    "status": e.get("status", "done"),
                                    "created_at": e.get("timestamp", e.get("created_at", "")),
                                    "processed_at": e.get("timestamp", ""),
                                    "priority": e.get("priority", 1),
                                })
                        elif isinstance(data, dict) and "events" in data:
                            for e in data["events"]:
                                all_events.append(e)
                except: pass
    except Exception as e:
        print(f"[VIZ] Error fetching events: {e}", flush=True)
    all_events.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return all_events[:limit]

def get_daemon_status():
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
    metrics = {}
    try:
        with open("/proc/loadavg") as f:
            metrics["load_avg"] = f.read().split()[:3]
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
        result = subprocess.run(["df", "/"], capture_output=True, text=True, timeout=5)
        lines = result.stdout.strip().split("\n")
        if len(lines) >= 2:
            parts = lines[1].split()
            metrics["disk_pct"] = int(parts[4].replace("%", ""))
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=index,name,temperature.gpu,utilization.gpu,memory.used,memory.total",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=5)
            gpus = []
            for line in result.stdout.strip().split("\n"):
                if line:
                    parts = [p.strip() for p in line.split(",")]
                    if len(parts) >= 6:
                        gpus.append({"id": parts[0],"name": parts[1],"temp": int(parts[2]),
                                     "util": int(parts[3]),"vram_used": int(parts[4]),"vram_total": int(parts[5])})
            metrics["gpus"] = gpus
        except Exception:
            metrics["gpus"] = []
    except Exception:
        pass
    return metrics

# ── WebSocket broadcast ──
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
    tick = 0
    while True:
        try:
            agents = get_agents()
            events = get_recent_events(20)
            bus_stats = get_bus_stats()
            daemons = get_daemon_status()
            data = {
                "type": "update", "tick": tick,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "agents": agents, "events": events, "bus_stats": bus_stats,
                "daemons": daemons, "uptime_seconds": int(time.time() - start_time),
            }
            broadcast(data)
            tick += 1
        except Exception as e:
            print(f"[ERROR] monitoring_loop: {e}", file=sys.stderr)
        time.sleep(2)

# ── Routes ──
@app.route("/hive")
def hive_page():
    return render_template("hive.html")

@app.route("/health")
def health():
    return jsonify({"status": "ok","service": "adam-viz-v4","agents": len(AGENTS_META),"clients_ws": len(ws_clients)})

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

@app.route("/api/chains")
def api_chains():
    events = get_bus_events(limit=60)
    chains = []
    for e in events:
        topic = e.get("topic", "")
        if "heartbeat" not in topic:
            chains.append({
                "id": e.get("id",""), "channel": topic, "source": e.get("source",""),
                "status": e.get("status","done"), "time": str(e.get("created_at",""))[11:19],
                "payload": json.dumps(e.get("payload",{}))[:200],
            })
    return jsonify({"chains": chains})

@sock.route("/ws")
def handle_ws(conn):
    ws_clients.add(conn)
    try:
        agents = get_agents()
        events = get_recent_events(20)
        bus_stats = get_bus_stats()
        daemons = get_daemon_status()
        initial = {"type": "init", "agents": agents, "events": events,
                   "bus_stats": bus_stats, "daemons": daemons,
                   "timestamp": datetime.now(timezone.utc).isoformat()}
        conn.send(json.dumps(initial))
        while True:
            msg = conn.receive()
            if msg is None:
                break
    except Exception:
        pass
    finally:
        ws_clients.discard(conn)

if __name__ == "__main__":
    t = threading.Thread(target=monitoring_loop, daemon=True)
    t.start()
    print("╔═══════════════════════════════════════════════╗")
    print("║  🐝  Adam-Viz V4  —  Go Bus API Dashboard    ║")
    print("╠═══════════════════════════════════════════════╣")
    print(f"║  Bus: {BUS_URL}")
    print("║  11 agents · Go Bus · PostgreSQL              ║")
    print("╚═══════════════════════════════════════════════╝")
    app.run(host="0.0.0.0", port=8084, debug=False, threaded=True)
