#!/usr/bin/env python3
"""doctor-watch.py — Handler ADAM v2 pour adam-doctor
Canal: service:restarted
Vérifie qu'un service redémarré fonctionne correctement après restart.
"""

import os
import sys
import json
import time
import socket
import subprocess
from datetime import datetime, timezone

CHANNEL = os.environ.get("ADAM_EVENT_CHANNEL", "unknown")
PAYLOAD = os.environ.get("ADAM_EVENT_PAYLOAD", "{}")
SOURCE = os.environ.get("ADAM_EVENT_SOURCE", "unknown")
ADAM_V2_DIR = os.environ.get("ADAM_V2_DIR", "/home/aza/eva-adam-v2")

LOG_DIR = os.path.join(ADAM_V2_DIR, "logs")
LOG_FILE = os.path.join(LOG_DIR, "doctor-handler.log")
os.makedirs(LOG_DIR, exist_ok=True)

# Services connus et comment les vérifier
KNOWN_SERVICES = {
    "event_daemon": {"type": "process", "pattern": "event_daemon.py"},
    "file_watcher": {"type": "process", "pattern": "file_watcher.py"},
    "self_heal": {"type": "process", "pattern": "self_heal.py"},
    "vllm": {"type": "port", "port": 8000},
    "ollama": {"type": "port", "port": 11434},
    "monitoring": {"type": "port", "port": 8081},
    "wiki": {"type": "port", "port": 8082},
    "rag": {"type": "port", "port": 8083},
    "adam-viz": {"type": "port", "port": 8084},
}


def log(msg: str):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(LOG_FILE, "a") as f:
        f.write(f"[{ts}] [doctor] {msg}\n")
    print(msg)


def check_process(pattern: str) -> bool:
    """Vérifie si un processus correspondant au pattern tourne."""
    try:
        result = subprocess.run(
            ["pgrep", "-f", pattern],
            capture_output=True, text=True, timeout=5
        )
        return result.returncode == 0 and bool(result.stdout.strip())
    except Exception:
        return False


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


def check_systemd(service: str) -> tuple[bool, str]:
    """Vérifie le statut d'un service systemd."""
    try:
        result = subprocess.run(
            ["systemctl", "is-active", service],
            capture_output=True, text=True, timeout=5
        )
        status = result.stdout.strip()
        return status == "active", status
    except Exception:
        return False, "unknown"


def main():
    log(f"Canal: {CHANNEL} | Source: {SOURCE}")

    try:
        payload = json.loads(PAYLOAD)
    except json.JSONDecodeError:
        payload = {}

    service_name = payload.get("service", payload.get("name", ""))
    log(f"Service redémarré: {service_name}")

    # Attendre un peu que le service démarre
    log("Attente 3s pour le démarrage...")
    time.sleep(3)

    if not service_name:
        log("⚠ Nom de service manquant dans le payload")
        print("doctor-watch: done (no service)")
        sys.exit(0)

    # Vérifier le service
    if service_name in KNOWN_SERVICES:
        svc = KNOWN_SERVICES[service_name]
        svc_type = svc["type"]

        if svc_type == "process":
            running = check_process(svc["pattern"])
            if running:
                log(f"✓ {service_name} — Processus en cours (pattern: {svc['pattern']})")
            else:
                log(f"✗ {service_name} — Processus introuvable (pattern: {svc['pattern']})")
                log(f"  Action: vérifier les logs ou redémarrer manuellement")

        elif svc_type == "port":
            port = svc["port"]
            if check_port(port):
                log(f"✓ {service_name} — Port {port} ouvert")
            else:
                log(f"✗ {service_name} — Port {port} fermé")
                log(f"  Action: vérifier les logs ou redémarrer le service")
    else:
        # Service inconnu — essayer systemd
        running, status = check_systemd(service_name)
        if running:
            log(f"✓ {service_name} — systemd: {status}")
        else:
            # Essayer pgrep avec le nom direct
            running = check_process(service_name)
            if running:
                log(f"✓ {service_name} — Processus trouvé via pgrep")
            else:
                log(f"⚠ {service_name} — Service inconnu et introuvable (status: {status})")
                log(f"  Vérification manuelle recommandée")

    # Santé globale du système
    log("Vérification santé globale...")
    daemons_ok = check_process("event_daemon.py") and check_process("file_watcher.py")
    log(f"  Daemons ADAM v2: {'OK' if daemons_ok else 'PROBLÈME'}")

    # GPU
    try:
        gpu_result = subprocess.run(
            ["nvidia-smi", "--query-gpu=index,temperature.gpu,utilization.gpu,memory.used,memory.total",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5
        )
        if gpu_result.returncode == 0:
            for line in gpu_result.stdout.strip().split("\n"):
                parts = [p.strip() for p in line.split(",")]
                if len(parts) >= 5:
                    gpu_id, temp, util, mem_used, mem_total = parts
                    log(f"  GPU {gpu_id}: {temp}°C, {util}% util, {mem_used}/{mem_total} MiB")
                    if int(temp) > 90:
                        log(f"    ⚠ GPU {gpu_id} TROP CHAUD ({temp}°C)")
                    if int(mem_total) > 0 and int(mem_used) / int(mem_total) > 0.95:
                        log(f"    ⚠ GPU {gpu_id} VRAM quasi-pleine ({mem_used}/{mem_total} MiB)")
    except Exception:
        log("  GPU: nvidia-smi indisponible")

    # Disk
    try:
        disk_result = subprocess.run(
            ["df", "-h", "/"],
            capture_output=True, text=True, timeout=5
        )
        if disk_result.returncode == 0:
            lines = disk_result.stdout.strip().split("\n")
            if len(lines) >= 2:
                parts = lines[1].split()
                if len(parts) >= 5:
                    log(f"  Disk /: {parts[2]} used / {parts[1]} total ({parts[4]})")
                    usage_pct = int(parts[4].rstrip("%"))
                    if usage_pct > 90:
                        log(f"    ⚠ Disk quasi-plein ({usage_pct}%)")
    except Exception:
        pass

    # ──────────────────────────────────────────
    # Surveillance des heartbeats agents
    # ──────────────────────────────────────────
    publish_path = os.path.join(ADAM_V2_DIR, "publish.py")
    log("Vérification heartbeats agents...")
    try:
        import sqlite3 as _sqlite3
        db_path = os.path.join(ADAM_V2_DIR, "event_bus.db")
        conn = _sqlite3.connect(db_path)
        conn.row_factory = _sqlite3.Row
        cur = conn.cursor()

        # Récupérer tous les agents avec leur dernier heartbeat
        cur.execute("""
            SELECT agent_id, status, heartbeat_at
            FROM agents
            ORDER BY agent_id
        """)
        agents = cur.fetchall()

        # Seuil: 5 minutes pour les agents proactifs (qui battent régulièrement)
        # Seuil: 30 minutes pour les agents réactifs (adam-cicd, adam-backup, adam-docs)
        REACTIVE_AGENTS = {"adam-cicd", "adam-backup", "adam-docs"}
        now = datetime.now(timezone.utc)
        dead_agents = []
        stale_agents = []

        for row in agents:
            aid = row["agent_id"]
            hb = row["heartbeat_at"]
            threshold_min = 30 if aid in REACTIVE_AGENTS else 5
            label = "réactif" if aid in REACTIVE_AGENTS else "proactif"

            if not hb:
                log(f"  {aid} — JAMAIS de heartbeat ({label})")
                dead_agents.append(aid)
                continue

            try:
                hb_dt = datetime.fromisoformat(hb.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                log(f"  {aid} — heartbeat illisible: {hb}")
                continue

            elapsed_sec = (now - hb_dt).total_seconds()
            elapsed_min = elapsed_sec / 60

            if elapsed_min > threshold_min:
                stale_agents.append((aid, elapsed_min, threshold_min, label))
                log(f"  ⚠ {aid} — pas de heartbeat depuis {elapsed_min:.0f}min (seuil {label}: {threshold_min}min)")
            else:
                log(f"  ✓ {aid} — heartbeat il y a {elapsed_min:.0f}min (seuil {label}: {threshold_min}min)")

        conn.close()

        # Publier des alertes pour les agents stale
        if stale_agents or dead_agents:
            stale_names = [a[0] for a in stale_agents] + dead_agents
            alert_payload = json.dumps({
                "type": "agent_stale",
                "agents": stale_names,
                "dead": dead_agents,
                "stale": [a[0] for a in stale_agents],
                "message": f"{len(stale_names)} agent(s) sans heartbeat récent",
                "checked_by": "adam-doctor"
            })
            try:
                subprocess.run(
                    ["python3", publish_path, "monitor:alert",
                     alert_payload,
                     "--source", "adam-doctor"],
                    capture_output=True, text=True, timeout=10
                )
                log(f"→ published monitor:alert pour {len(stale_names)} agent(s) stale: {', '.join(stale_names)}")

                # Publier aussi sur adam:error pour que self_heal corrige les agents stale
                for agent_name, stale_minutes in stale_agents:
                    # Trouver le handler_path depuis la config de l'agent
                    handler_path = ""
                    try:
                        agent_row = conn.execute(
                            "SELECT config FROM agents WHERE agent_id = ?",
                            (agent_name,)
                        ).fetchone()
                        if agent_row and agent_row[0]:
                            cfg = json.loads(agent_row[0])
                            handler_path = cfg.get("handler", "")
                    except Exception:
                        pass

                    error_payload = json.dumps({
                        "agent_id": agent_name,
                        "error_type": "agent_stale",
                        "stale_minutes": int(stale_minutes),
                        "handler_path": handler_path,
                        "message": f"{agent_name} sans heartbeat depuis {int(stale_minutes)}min"
                    })
                    try:
                        subprocess.run(
                            ["python3", publish_path, "adam:error",
                             error_payload,
                             "--source", "adam-doctor"],
                            capture_output=True, text=True, timeout=10
                        )
                        log(f"  → published adam:error pour {agent_name} (stale {int(stale_minutes)}min)")
                    except Exception as e:
                        log(f"  ⚠ Échec publication adam:error pour {agent_name}: {e}")
            except Exception as e:
                log(f"⚠ Échec publication alerte stale: {e}")
        else:
            log("  Tous les agents ont un heartbeat récent ✓")

    except Exception as e:
        log(f"⚠ Erreur surveillance heartbeats: {e}")

    # Vérification post-redémarrage terminée
    log("Vérification post-redémarrage terminée")

    # ──────────────────────────────────────────
    # Follow-up event — chaîne entre agents
    # ──────────────────────────────────────────
    try:
        subprocess.run(
            ["python3", publish_path, "dashboard:down",
             json.dumps({"service": service_name or "unknown", "checked_by": "adam-doctor"}),
             "--source", "adam-doctor"],
            capture_output=True, text=True, timeout=10
        )
        log("→ published dashboard:down for adam-viz-checker")
    except Exception as e:
        log(f"⚠ Échec publication follow-up: {e}")

    print("doctor-watch: done")
    sys.exit(0)


if __name__ == "__main__":
    main()
