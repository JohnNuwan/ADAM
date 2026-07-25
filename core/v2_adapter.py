#!/usr/bin/env python3
"""
Adaptateur v2 — Enveloppe les scripts ADAM v1 dans le bus d'événements v2.

Chaque script v1 est exécuté tel quel (sans modification). L'adaptateur:
  1. Enregistre un heartbeat avant exécution (adam:heartbeat)
  2. Exécute le script v1 original via subprocess
  3. Capture stdout/stderr/exit_code/durée
  4. Publie le résultat sur les canaux appropriés (selon config agent)
  5. Met à jour AgentState (record_run, set_state, record_health)
  6. Publie adam:error en cas d'échec, adam:recovered sinon

Usage:
  python3 v2_adapter.py <agent_id> [--script-args ...]
  python3 v2_adapter.py adam-praetor -- --once
  python3 v2_adapter.py --list          # Lister les agents configurés
  python3 v2_adapter.py --test-all      # Tester tous les agents (dry-run)

Aucun script v1 n'est modifié. L'adaptateur est l'unique point d'entrée v2.
"""

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# ─── Import des modules v2 ────────────────────────────────────────────
V2_DIR = Path(__file__).parent
sys.path.insert(0, str(V2_DIR))

from event_bus import EventBus, CHANNELS
from state_isolation import AgentState

# ─── Configuration des 8 agents ADAM ──────────────────────────────────
# Chaque entrée mappe un agent_id v2 vers:
#   - script: chemin du script v1 original
#   - channels: canaux à publier selon le résultat (succès/échec)
#   - state_keys: clés AgentState à maintenir
#   - timeout: délai max d'exécution (secondes)

AGENTS_CONFIG = {
    "adam-praetor": {
        "script": "~/scripts/praetor-watch.sh",
        "args_default": ["--once"],
        "channels_success": ["adam:heartbeat"],
        "channels_error": ["hardware:gpu_alert", "hardware:ram_alert", "hardware:disk_alert", "adam:error"],
        "channels_parse": True,  # Parser stdout pour publier des alertes ciblées
        "state_keys": ["last_run", "gpu_temp", "vram_usage", "ram_usage", "disk_usage"],
        "timeout": 120,
    },
    "adam-blue": {
        "script": "~/scripts/blue-watch.sh",
        "args_default": ["--once"],
        "channels_success": ["adam:heartbeat"],
        "channels_error": ["security:permission_drift", "security:suid_change", "adam:error"],
        "channels_parse": True,
        "state_keys": ["last_run", "open_ports", "failed_logins", "suid_count"],
        "timeout": 120,
    },
    "adam-doctor": {
        "script": "~/scripts/doctor-watch.py",
        "args_default": [],
        "channels_success": ["adam:heartbeat"],
        "channels_error": ["cron:missed", "adam:error"],
        "channels_parse": True,
        "state_keys": ["last_run", "crons_checked", "crons_failed", "crons_healed"],
        "timeout": 90,
    },
    "adam-viz-checker": {
        "script": "~/scripts/viz-checker.py",
        "args_default": [],
        "channels_success": ["adam:heartbeat"],
        "channels_error": ["dashboard:down", "dashboard:slow", "adam:error"],
        "channels_parse": True,
        "state_keys": ["last_run", "dashboards_checked", "dashboards_ok", "dashboards_fail"],
        "timeout": 180,
    },
    "adam-sentinel": {
        "script": "~/scripts/sentinel-watch.sh",
        "args_default": [],
        "channels_success": ["adam:heartbeat", "update:available"],
        "channels_error": ["adam:error"],
        "channels_parse": False,
        "state_keys": ["last_run", "sites_checked", "reports_generated"],
        "timeout": 300,
    },
    "adam-backup": {
        "script": "~/scripts/backup.sh",
        "args_default": [],
        "channels_success": ["backup:done", "adam:heartbeat"],
        "channels_error": ["backup:failed", "adam:error"],
        "channels_parse": False,
        "state_keys": ["last_run", "backup_size", "backup_path", "backups_retained"],
        "timeout": 600,
    },
    "adam-critic": {
        "script": "~/scripts/critic-review.sh",
        "args_default": ["--quick"],
        "channels_success": ["adam:heartbeat", "test:passed"],
        "channels_error": ["skill:broken", "test:failed", "adam:error"],
        "channels_parse": True,
        "state_keys": ["last_run", "skills_checked", "skills_broken", "tests_passed", "tests_failed"],
        "timeout": 300,
    },
    "adam-red": {
        "script": "~/scripts/osint-email.sh",
        "args_default": [],
        "channels_success": ["adam:heartbeat"],
        "channels_error": ["adam:error"],
        "channels_parse": False,
        "state_keys": ["last_run", "target", "findings_count"],
        "timeout": 300,
    },
}

# ─── Patterns de parsing stdout ──────────────────────────────────────
# Détecte des alertes dans la sortie des scripts v1 et publie sur le bon canal
PARSE_PATTERNS = {
    "adam-praetor": [
        (r"VRAM.*?(\d+)%.*?(?:alert|warn|crit)", "hardware:gpu_alert", "VRAM: {match}%"),
        (r"RAM.*?(\d+)%.*?(?:alert|warn|crit)", "hardware:ram_alert", "RAM: {match}%"),
        (r"disque.*?(\d+)%.*?(?:alert|warn|crit)", "hardware:disk_alert", "Disque: {match}%"),
        (r"GPU.*?temp.*?(\d+).*?(?:alert|warn|crit)", "hardware:gpu_alert", "GPU temp: {match}°C"),
    ],
    "adam-blue": [
        (r"port.*?(\d+).*?(?:ouvert|open)", "security:permission_drift", "Port ouvert: {match}"),
        (r"SUID.*?(?:nouveau|new).*?(\d+)", "security:suid_change", "Nouveau SUID: {match}"),
        (r"permission.*?(?:drift|change)", "security:permission_drift", "Dérive de permissions détectée"),
    ],
    "adam-doctor": [
        (r"cron.*?(?:missed|manqué|échec|fail)", "cron:missed", "Cron manqué: {match}"),
    ],
    "adam-viz-checker": [
        (r"dashboard.*?(?:down|injoignable|fail|ERROR)", "dashboard:down", "Dashboard down: {match}"),
        (r"latency.*?(\d+).*?(?:slow|lent)", "dashboard:slow", "Dashboard lent: {match}ms"),
    ],
    "adam-critic": [
        (r"skill.*?(?:broken|cassé|syntax)", "skill:broken", "Skill cassé: {match}"),
        (r"test.*?(?:failed|échec|FAIL)", "test:failed", "Test échoué: {match}"),
        (r"test.*?(?:passed|succès|PASS|OK)", "test:passed", "Test passé: {match}"),
    ],
}


def log(msg: str, level: str = "INFO"):
    """Log avec horodatage UTC."""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] [{level}] v2_adapter: {msg}", flush=True)


def resolve_path(p: str) -> str:
    """Résout un chemin avec ~ et variables d'environnement."""
    return os.path.expanduser(os.path.expandvars(p))


def parse_stdout_alerts(agent_id: str, stdout: str, bus: EventBus):
    """
    Parse la sortie stdout du script v1 pour détecter des alertes
    et publier des événements ciblés sur les canaux appropriés.
    """
    import re
    patterns = PARSE_PATTERNS.get(agent_id, [])
    if not patterns:
        return

    for line in stdout.splitlines():
        for pattern, channel, template in patterns:
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                # Extraire le groupe capturé ou toute la ligne
                value = match.group(1) if match.groups() else line.strip()
                payload = {
                    "agent": agent_id,
                    "alert": template.format(match=value),
                    "raw_line": line.strip(),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                bus.publish(channel, payload, source=agent_id, priority=1)
                log(f"Alerte parsée → {channel}: {payload['alert']}", "WARN")


def run_agent(
    agent_id: str,
    extra_args: list = None,
    dry_run: bool = False,
    bus: EventBus = None,
    state: AgentState = None,
) -> dict:
    """
    Exécute un agent ADAM v1 via l'adaptateur v2.

    Returns:
        dict avec: agent_id, exit_code, stdout, stderr, duration, events_published
    """
    config = AGENTS_CONFIG.get(agent_id)
    if not config:
        log(f"Agent inconnu: {agent_id}", "ERROR")
        return {"agent_id": agent_id, "exit_code": -1, "error": "Agent non configuré"}

    script_path = resolve_path(config["script"])
    args = config["args_default"] + (extra_args or [])
    timeout = config["timeout"]

    # Initialiser bus et state si non fournis
    if bus is None:
        bus = EventBus()
    if state is None:
        state = AgentState(agent_id)

    # ─── 1. Heartbeat avant exécution ────────────────────────────────
    hb_payload = {
        "agent": agent_id,
        "status": "starting",
        "script": script_path,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    bus.publish("adam:heartbeat", hb_payload, source=agent_id, priority=0)
    state.record_health("starting")

    log(f"Démarrage agent {agent_id} → {script_path} {' '.join(args)}")

    if dry_run:
        log(f"DRY-RUN: {agent_id} — script non exécuté", "WARN")
        state.set_state("last_run_status", "dry_run")
        state.record_health("dry_run")
        return {
            "agent_id": agent_id,
            "exit_code": 0,
            "stdout": "[dry-run]",
            "stderr": "",
            "duration": 0,
            "events_published": 1,
            "dry_run": True,
        }

    # ─── 2. Exécution du script v1 ───────────────────────────────────
    cmd = ["bash", script_path] + args
    if script_path.endswith(".py"):
        cmd = ["python3", script_path] + args

    if not os.path.isfile(script_path):
        log(f"Script introuvable: {script_path}", "ERROR")
        state.set_state("last_run_status", "script_missing")
        state.record_health("error")
        err_payload = {
            "agent": agent_id,
            "error": f"Script introuvable: {script_path}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        bus.publish("adam:error", err_payload, source=agent_id, priority=2)
        return {"agent_id": agent_id, "exit_code": -1, "error": "Script introuvable"}

    events_published = 1  # heartbeat déjà publié
    start_time = time.monotonic()

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env={**os.environ, "ADAM_V2": "1", "ADAM_V2_AGENT_ID": agent_id},
        )
        duration = time.monotonic() - start_time
        exit_code = result.returncode
        stdout = result.stdout
        stderr = result.stderr

    except subprocess.TimeoutExpired:
        duration = time.monotonic() - start_time
        log(f"TIMEOUT: {agent_id} après {timeout}s", "ERROR")
        state.set_state("last_run_status", "timeout")
        state.record_health("timeout")
        err_payload = {
            "agent": agent_id,
            "error": f"Timeout après {timeout}s",
            "duration": duration,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        bus.publish("adam:error", err_payload, source=agent_id, priority=2)
        events_published += 1
        return {
            "agent_id": agent_id,
            "exit_code": -2,
            "stdout": "",
            "stderr": f"Timeout après {timeout}s",
            "duration": duration,
            "events_published": events_published,
        }

    # ─── 3. Parsing stdout pour alertes ciblées ──────────────────────
    if config.get("channels_parse") and stdout:
        parse_stdout_alerts(agent_id, stdout, bus)

    # ─── 4. Publication du résultat ──────────────────────────────────
    if exit_code == 0:
        # Succès
        for channel in config["channels_success"]:
            payload = {
                "agent": agent_id,
                "exit_code": exit_code,
                "duration": round(duration, 2),
                "stdout_tail": stdout[-500:] if stdout else "",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            bus.publish(channel, payload, source=agent_id, priority=0)
            events_published += 1

        # Publier adam:recovered si l'état précédent était error
        prev_status = state.get_state("last_run_status")
        if prev_status == "error":
            bus.publish("adam:recovered", {
                "agent": agent_id,
                "previous_status": prev_status,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }, source=agent_id, priority=1)
            events_published += 1

        state.set_state("last_run_status", "success")
        state.record_health("healthy")
        log(f"✅ {agent_id} terminé en {duration:.1f}s — {events_published} événements publiés")

    else:
        # Échec
        for channel in config["channels_error"]:
            if channel == "adam:error":
                continue  # Publié ci-dessous
            payload = {
                "agent": agent_id,
                "exit_code": exit_code,
                "stderr_tail": stderr[-500:] if stderr else "",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            bus.publish(channel, payload, source=agent_id, priority=1)
            events_published += 1

        # Publier adam:error
        err_payload = {
            "agent": agent_id,
            "exit_code": exit_code,
            "stderr": stderr[-1000:] if stderr else "",
            "stdout_tail": stdout[-500:] if stdout else "",
            "duration": round(duration, 2),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        bus.publish("adam:error", err_payload, source=agent_id, priority=2)
        events_published += 1

        state.set_state("last_run_status", "error")
        state.record_health("error")
        log(f"❌ {agent_id} échec (exit={exit_code}) en {duration:.1f}s — {events_published} événements", "ERROR")

    # ─── 5. Mise à jour AgentState ───────────────────────────────────
    state.set_state("last_run", datetime.now(timezone.utc).isoformat())
    state.set_state("last_exit_code", str(exit_code))
    state.set_state("last_duration", f"{duration:.2f}")
    state.set_state("last_stdout_tail", stdout[-200:] if stdout else "")
    state.set_state("last_stderr_tail", stderr[-200:] if stderr else "")

    # record_run(action: str, result: str, duration_ms: float)
    state.record_run(
        action="run",
        result="OK" if exit_code == 0 else "FAIL",
        duration_ms=duration * 1000,
    )

    return {
        "agent_id": agent_id,
        "exit_code": exit_code,
        "stdout": stdout,
        "stderr": stderr,
        "duration": round(duration, 2),
        "events_published": events_published,
    }


def list_agents():
    """Affiche la liste des agents configurés."""
    print(f"{'Agent':<20} {'Script':<35} {'Timeout':<10} {'Canaux succès':<25} {'Canaux erreur'}")
    print("─" * 120)
    for agent_id, cfg in AGENTS_CONFIG.items():
        script = cfg["script"]
        timeout = f"{cfg['timeout']}s"
        ch_ok = ", ".join(cfg["channels_success"])
        ch_err = ", ".join(cfg["channels_error"])
        print(f"{agent_id:<20} {script:<35} {timeout:<10} {ch_ok:<25} {ch_err}")


def test_all_agents():
    """Test dry-run de tous les agents — vérifie que les scripts existent."""
    print("\n🧪 Test dry-run des 8 agents ADAM v2\n")
    results = []
    bus = EventBus()
    for agent_id in AGENTS_CONFIG:
        state = AgentState(agent_id)
        result = run_agent(agent_id, dry_run=True, bus=bus, state=state)
        results.append(result)
        script_path = resolve_path(AGENTS_CONFIG[agent_id]["script"])
        exists = "✅" if os.path.isfile(script_path) else "❌"
        print(f"  {exists} {agent_id:<20} script={'OK' if exists == '✅' else 'MANQUANT'}")

    # Vérifier que les canaux publiés existent dans CHANNELS
    print("\n📋 Vérification des canaux:")
    all_channels = set()
    for cfg in AGENTS_CONFIG.values():
        all_channels.update(cfg["channels_success"])
        all_channels.update(cfg["channels_error"])
    for ch in sorted(all_channels):
        valid = "✅" if ch in CHANNELS else "❌"
        print(f"  {valid} {ch}")

    print(f"\nTotal: {len(results)} agents testés (dry-run)")


def main():
    parser = argparse.ArgumentParser(
        description="Adaptateur v2 — Enveloppe les scripts ADAM v1 dans le bus d'événements v2",
    )
    parser.add_argument("agent_id", nargs="?", help="ID de l'agent à exécuter (ex: adam-praetor)")
    parser.add_argument("--", dest="script_args", nargs=argparse.REMAINDER, help="Arguments passés au script v1")
    parser.add_argument("--list", action="store_true", help="Lister les agents configurés")
    parser.add_argument("--test-all", action="store_true", help="Tester tous les agents (dry-run)")
    parser.add_argument("--dry-run", action="store_true", help="Ne pas exécuter le script v1")
    parser.add_argument("--json", action="store_true", help="Sortie JSON au lieu de texte")

    args = parser.parse_args()

    if args.list:
        list_agents()
        return

    if args.test_all:
        test_all_agents()
        return

    if not args.agent_id:
        parser.print_help()
        return

    if args.agent_id not in AGENTS_CONFIG:
        print(f"❌ Agent inconnu: {args.agent_id}")
        print(f"Agents disponibles: {', '.join(AGENTS_CONFIG.keys())}")
        sys.exit(1)

    # Arguments après -- vont au script v1
    extra_args = args.script_args[1:] if args.script_args else []

    result = run_agent(
        args.agent_id,
        extra_args=extra_args,
        dry_run=args.dry_run,
    )

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"\n{'✅' if result['exit_code'] == 0 else '❌'} {result['agent_id']}: exit={result['exit_code']}, "
              f"durée={result.get('duration', 0):.1f}s, événements={result.get('events_published', 0)}")


if __name__ == "__main__":
    main()
