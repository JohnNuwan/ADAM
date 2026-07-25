#!/usr/bin/env python3
"""ADAM Agent Daemon V5 — Lance les agents via Runtime V5 (LLM Qwen2.5-32B)"""
import subprocess, time, json, urllib.request, sys, os, logging, fcntl
from pathlib import Path
from datetime import datetime, timezone

BASE = Path(os.environ.get("ADAM_V2_DIR", "/home/aza/eva-adam-v2"))
GO_BUS = os.environ.get("GO_BUS_URL", "http://localhost:8086/api/publish")
LOG_FILE = Path("/tmp/adam-daemon.log")
PID_FILE = Path("/tmp/adam-daemon.pid")
LOCK_FILE = Path("/tmp/adam-daemon.lock")
AGENT_TIMEOUT = int(os.environ.get("ADAM_AGENT_TIMEOUT", "180"))
VLLM_URL = os.environ.get("VLLM_URL", "http://localhost:8000")
RUNTIME_V5 = Path("/home/aza/eva-adam-v2/core/v5/adam_runtime.py")

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] [daemon] %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(str(LOG_FILE))
    ]
)
logger = logging.getLogger(__name__)

AGENTS = [
    "praetor", "sentinel", "critic", "scribe", "skillsmith",
    "doctor", "treasurer", "social", "osint", "researcher",
    "rag", "viz", "ctf", "blue-team", "red-team"
]

MISSIONS = {
    "praetor": "Vérifie l'état du système et corrige les erreurs",
    "sentinel": "Scanne les 3 dernières CVE et crée un rapport",
    "critic": "Audite la qualité du code des agents",
    "scribe": "Rédige un rapport de l'état du système",
    "skillsmith": "Crée un nouveau skill pour un domaine manquant",
    "doctor": "Diagnostique les conteneurs Docker",
    "treasurer": "Analyse les stratégies pour Freedom24",
    "social": "Propose 3 posts Instagram pour Maeve.tech",
    "osint": "Collecte des informations sur une cible",
    "researcher": "Recherche les dernières publications sur les agents IA",
    "rag": "Indexe les documents et crée une recherche sémantique",
    "viz": "Vérifie le dashboard 3D et propose des améliorations",
    "ctf": "Analyse un challenge CTF et propose une solution",
    "blue-team": "Analyse les vulnérabilités du serveur",
    "red-team": "Crée un outil de scan de sécurité"
}

def _acquire_lock():
    if LOCK_FILE.exists():
        LOCK_FILE.unlink()
    fd = os.open(str(LOCK_FILE), os.O_CREAT | os.O_RDWR)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except (IOError, OSError):
        logger.error("Un autre daemon tourne déjà. Arrêt.")
        sys.exit(1)

def publish_packet(agent, exit_code, output, status):
    """Publish packet with real agent output (thoughts, tools, results)"""
    # Extract real info from output
    thought = ""
    tools_created = []
    mission = ""

    if output:
        lines = output.strip().split("\n")
        for line in lines[:5]:
            if "reçoit la mission:" in line:
                mission = line.split("mission:")[-1].strip()[:100]
            if "create_tool" in line:
                # Extract tool name
                import re
                m = re.search(r'"tool":\s*"([^"]+)"', line)
                if m:
                    tools_created.append(m.group(1))
            if "execute_tool" in line:
                import re
                m = re.search(r'"tool":\s*"([^"]+)"', line)
                if m:
                    tools_created.append("exec:" + m.group(1))

    # Build a meaningful thought
    parts = []
    if mission:
        parts.append(f"Mission: {mission}")
    if tools_created:
        parts.append(f"Outils: {', '.join(tools_created[:3])}")
    if not parts:
        parts.append(output[:100] if output else status)

    thought = " | ".join(parts)

    payload = json.dumps({
        "topic": "adam:packet",
        "source": agent,
        "payload": {
            "exit": exit_code,
            "thought": thought[:200],
            "mission": mission[:100],
            "tools_created": tools_created[:5],
            "output": output[:300],
            "status": status,
            "time": datetime.now(timezone.utc).isoformat()
        },
        "priority": 1
    }).encode()
    try:
        req = urllib.request.Request(GO_BUS, data=payload, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=3)
    except:
        pass

def run_cycle():
    agent_dir = BASE / "agents"
    env = dict(os.environ, VLLM_URL=VLLM_URL)

    for agent in AGENTS:
        if RUNTIME_V5.exists():
            mission = MISSIONS.get(agent, "")
            logger.info(f"Lancement {agent} via Runtime V5 (LLM)...")

            try:
                result = subprocess.run(
                    ["python3", str(RUNTIME_V5), "adam-" + agent if not agent.startswith("adam-") else agent, "-m", mission],
                    capture_output=True,
                    text=True,
                    timeout=AGENT_TIMEOUT,
                    env=env
                )
                exit_code = result.returncode
                output = result.stdout.strip()
                error = result.stderr.strip()

                if exit_code == 0:
                    logger.info(f"{agent}: OK (LLM) - {output[:150]}")
                else:
                    logger.warning(f"{agent}: exit={exit_code} - {error[:200]}")

                # Publish with full output (not truncated)
                publish_packet(agent, exit_code, output[:500], "done" if exit_code == 0 else "failed")

            except subprocess.TimeoutExpired:
                logger.warning(f"{agent}: timeout après {AGENT_TIMEOUT}s")
                publish_packet(agent, 124, "", "timeout")
            except Exception as e:
                logger.error(f"{agent}: erreur {e}")
                publish_packet(agent, 1, "", "error")
        else:
            # Fallback: script classique
            script = agent_dir / agent / f"adam-{agent}.py"
            if not script.exists():
                script = agent_dir / agent / f"{agent}.py"
            if not script.exists():
                script = agent_dir / agent / "watch.py"
            if not script.exists():
                continue

            logger.info(f"Lancement {agent} (script)...")
            try:
                result = subprocess.run(
                    ["python3", str(script), "--mission", MISSIONS.get(agent, "")],
                    capture_output=True, text=True, timeout=60
                )
                publish_packet(agent, result.returncode, result.stdout[:200], "done" if result.returncode == 0 else "failed")
                logger.info(f"{agent}: exit={result.returncode}")
            except subprocess.TimeoutExpired:
                publish_packet(agent, 124, "", "timeout")
                logger.warning(f"{agent}: timeout 60s")
            except Exception as e:
                publish_packet(agent, 1, "", "error")
                logger.error(f"{agent}: {e}")

    # Heartbeat
    payload = json.dumps({"topic": "adam:heartbeat", "source": "daemon", "payload": {"cycle": "done"}, "priority": 0}).encode()
    try:
        req = urllib.request.Request(GO_BUS, data=payload, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=3)
    except:
        pass

def main():
    _acquire_lock()
    PID_FILE.write_text(str(os.getpid()))
    logger.info(f"ADAM Daemon V5 — PID={os.getpid()} — {len(AGENTS)} agents — timeout={AGENT_TIMEOUT}s")
    logger.info(f"Runtime V5: {RUNTIME_V5} ({'OK' if RUNTIME_V5.exists() else 'NOT FOUND'})")
    logger.info(f"VLLM URL: {VLLM_URL}")

    cycle = 0
    while True:
        logger.info(f"--- Cycle {cycle} ---")
        run_cycle()
        cycle += 1
        time.sleep(10)

if __name__ == "__main__":
    main()
