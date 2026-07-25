#!/usr/bin/env python3
"""viz-checker.py — Handler ADAM v2 pour adam-viz-checker
Canaux: dashboard:down, dashboard:slow
Vérifie l'état des dashboards EVA (ports 8081-8084).
"""

import os
import sys
import json
import time
import urllib.request
import urllib.error
import socket
from datetime import datetime, timezone

CHANNEL = os.environ.get("ADAM_EVENT_CHANNEL", "unknown")
PAYLOAD = os.environ.get("ADAM_EVENT_PAYLOAD", "{}")
SOURCE = os.environ.get("ADAM_EVENT_SOURCE", "unknown")
ADAM_V2_DIR = os.environ.get("ADAM_V2_DIR", "/home/aza/eva-adam-v2")

LOG_DIR = os.path.join(ADAM_V2_DIR, "logs")
LOG_FILE = os.path.join(LOG_DIR, "viz-handler.log")
os.makedirs(LOG_DIR, exist_ok=True)

# Dashboards connus
DASHBOARDS = {
    "monitoring": {"port": 8081, "name": "Monitoring (Chart.js)"},
    "wiki": {"port": 8082, "name": "Wiki D3.js"},
    "rag": {"port": 8083, "name": "RAG Search"},
    "adam-viz": {"port": 8084, "name": "Adam-Viz 3D (Three.js)"},
}

# Seuil de latence en secondes pour dashboard:slow
SLOW_THRESHOLD = 3.0


def log(msg: str):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(LOG_FILE, "a") as f:
        f.write(f"[{ts}] [viz-checker] {msg}\n")
    print(msg)


def check_port(port: int, timeout: float = 2.0) -> bool:
    """Vérifie si un port est ouvert."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex(("127.0.0.1", port))
        sock.close()
        return result == 0
    except Exception:
        return False


def check_http(port: int, timeout: float = 3.0) -> tuple[bool, float]:
    """Tente une requête HTTP GET. Retourne (ok, latence)."""
    url = f"http://127.0.0.1:{port}/"
    start = time.time()
    try:
        req = urllib.request.Request(url, method="GET")
        resp = urllib.request.urlopen(req, timeout=timeout)
        latency = time.time() - start
        return resp.status == 200, latency
    except urllib.error.HTTPError:
        latency = time.time() - start
        # HTTP error = serveur répond mais erreur (ex: 404) — c'est "up"
        return True, latency
    except Exception:
        latency = time.time() - start
        return False, latency


def main():
    log(f"Canal: {CHANNEL} | Source: {SOURCE}")

    # Parser le payload
    try:
        payload = json.loads(PAYLOAD)
    except json.JSONDecodeError:
        payload = {}

    target_dash = payload.get("dashboard", payload.get("name", ""))
    log(f"Dashboard ciblé: {target_dash or 'tous'}")

    case_handled = False

    if CHANNEL == "dashboard:down":
        case_handled = True
        log("Vérification des dashboards down...")

        for dash_id, info in DASHBOARDS.items():
            port = info["port"]
            port_open = check_port(port)
            if port_open:
                http_ok, latency = check_http(port)
                if http_ok:
                    log(f"✓ {info['name']} (:{port}) — UP ({latency:.2f}s)")
                else:
                    log(f"⚠ {info['name']} (:{port}) — Port ouvert mais HTTP ne répond pas")
            else:
                log(f"✗ {info['name']} (:{port}) — DOWN")

        # Si un dashboard spécifique est down, suggérer un restart
        if target_dash and target_dash in DASHBOARDS:
            port = DASHBOARDS[target_dash]["port"]
            if not check_port(port):
                log(f"Action suggérée: redémarrer le dashboard {target_dash}")
                # Les dashboards sont des processus Python, pas systemd
                # On peut identifier le PID via le port
                try:
                    import subprocess
                    result = subprocess.run(
                        ["fuser", f"{port}/tcp"],
                        capture_output=True, text=True, timeout=5
                    )
                    if result.stdout.strip():
                        log(f"PID sur le port {port}: {result.stdout.strip()}")
                except Exception:
                    pass

    elif CHANNEL == "dashboard:slow":
        case_handled = True
        log(f"Vérification de la latence (seuil: {SLOW_THRESHOLD}s)...")

        for dash_id, info in DASHBOARDS.items():
            port = info["port"]
            if check_port(port):
                ok, latency = check_http(port, timeout=5.0)
                if latency > SLOW_THRESHOLD:
                    log(f"⚠ {info['name']} (:{port}) — LENT ({latency:.2f}s > {SLOW_THRESHOLD}s)")
                    # Suggérer des actions
                    log(f"  Actions possibles: check CPU/ram, redémarrer le dashboard")
                else:
                    log(f"✓ {info['name']} (:{port}) — OK ({latency:.2f}s)")
            else:
                log(f"✗ {info['name']} (:{port}) — DOWN (ne répond pas)")

    else:
        if not case_handled:
            log(f"Canal non reconnu: {CHANNEL}")

    log("Vérification terminée")
    print("viz-checker: done")
    sys.exit(0)


if __name__ == "__main__":
    main()
