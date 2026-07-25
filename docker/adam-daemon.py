#!/usr/bin/env python3
"""ADAM Agent Daemon V5.1 — Lit les missions depuis le Go Bus + missions évolutives"""
import subprocess, time, json, urllib.request, sys, os, logging, fcntl, random
from pathlib import Path
from datetime import datetime, timezone

BASE = Path(os.environ.get("ADAM_V2_DIR", "/home/aza/eva-adam-v2"))
GO_BUS = os.environ.get("GO_BUS_URL", "http://localhost:8086/api/publish")
BUS_QUERY = os.environ.get("GO_BUS_QUERY", "http://localhost:8086/api/query")
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
    handlers=[logging.StreamHandler(sys.stdout), logging.FileHandler(str(LOG_FILE))]
)
logger = logging.getLogger(__name__)

AGENTS = [
    "praetor", "sentinel", "critic", "scribe", "skillsmith",
    "doctor", "treasurer", "social", "osint", "researcher",
    "rag", "viz", "ctf", "blue-team", "red-team"
]

# Missions par défaut (fallback si pas de mission dans le bus)
DEFAULT_MISSIONS = {
    "praetor": "Vérifie l'état du système et propose des corrections",
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

# Missions évolutives (basées sur les leçons apprises)
EVOLUTION_MISSIONS = {
    "sentinel": [
        "Scanne les 3 dernières CVE et crée un rapport",
        "Améliore le scanner CVE pour couvrir plus de sources",
        "Crée un outil de veille automatisée qui tourne en continu",
        "Analyse les tendances des vulnérabilités de la semaine",
    ],
    "ctf": [
        "Analyse un challenge CTF et propose une solution",
        "Crée un nouveau challenge CTF pour les autres agents",
        "Documente les techniques apprises des derniers CTF",
        "Crée un outil de génération de challenges CTF",
    ],
    "red-team": [
        "Crée un outil de scan de sécurité",
        "Améliore le scanner pour détecter plus de vulnérabilités",
        "Crée un outil de test d'intrusion automatisé",
        "Analyse les résultats du dernier scan et propose des corrections",
    ],
    "blue-team": [
        "Analyse les vulnérabilités du serveur",
        "Propose un plan de hardening basé sur les derniers scans",
        "Crée un outil de monitoring de sécurité",
        "Vérifie que les corrections précédentes ont été appliquées",
    ],
    "social": [
        "Propose 3 posts Instagram pour Maeve.tech",
        "Analyse les tendances actuelles sur Instagram",
        "Crée un calendrier éditorial pour la semaine",
        "Améliore le générateur de posts avec de nouveaux templates",
    ],
    "treasurer": [
        "Analyse les stratégies pour Freedom24",
        "Crée un outil de tracking de portefeuille",
        "Analyse les tendances du marché actuel",
        "Propose une stratégie d'allocation basée sur les dernières données",
    ],
    "researcher": [
        "Recherche les dernières publications sur les agents IA",
        "Analyse les 5 papers les plus importants de la semaine",
        "Propose des améliorations pour ADAM basées sur la recherche",
        "Crée un outil de veille académique automatisée",
    ],
    "praetor": [
        "Vérifie l'état du système et propose des corrections",
        "Analyse les performances des agents et propose des optimisations",
        "Crée un plan d'évolution pour le système ADAM",
        "Vérifie que les corrections précédentes fonctionnent",
    ],
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

def publish_packet(agent, exit_code, output, status, thought="", mission="", tools=None):
    """Publish packet with real agent output"""
    if not thought:
        # Extract thought from output
        if output:
            lines = output.strip().split("\n")
            for line in lines[:5]:
                if "reçoit la mission:" in line:
                    mission = line.split("mission:")[-1].strip()[:100]
                    break
        thought = f"Mission: {mission[:60]}" if mission else (output[:100] if output else status)
        if tools:
            thought += f" | Outils: {', '.join(tools[:3])}"

    payload = json.dumps({
        "topic": "adam:packet",
        "source": agent,
        "payload": {
            "exit": exit_code,
            "thought": thought[:200],
            "mission": mission[:100],
            "tools_created": tools or [],
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

def fetch_mission_from_bus(agent):
    """Read pending missions for this agent from Go Bus"""
    try:
        agent_name = "adam-" + agent if not agent.startswith("adam-") else agent
        req = urllib.request.Request(f"{BUS_QUERY}?limit=20&topic=adam:mission")
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode())
            missions = data if isinstance(data, list) else data.get("events", [])
            agent_lower = agent_name.lower()
            agent_short = agent.lower().replace("adam-", "")
            for m in missions:
                payload = m.get("payload", {})
                if isinstance(payload, dict):
                    target_agent = str(payload.get("agent", "")).lower()
                    mission = payload.get("mission", "")
                    status = payload.get("status", "")
                    # Case-insensitive matching
                    if target_agent == agent_lower or target_agent == agent_short or target_agent == agent.lower():
                        if status == "pending" and mission:
                            logger.info(f"Mission du bus pour {agent}: {mission[:80]}")
                            return mission
    except Exception as e:
        logger.debug(f"fetch_mission error: {e}")
    return None

def get_evolutionary_mission(agent, cycle):
    """Get an evolutionary mission based on cycle number and lessons"""
    if agent in EVOLUTION_MISSIONS:
        missions = EVOLUTION_MISSIONS[agent]
        idx = cycle % len(missions)
        return missions[idx]
    return DEFAULT_MISSIONS.get(agent, "Exécute ta mission")

def get_agent_mission(agent, cycle):
    """Get mission: 1) from Go Bus, 2) evolutionary, 3) default"""
    # Try Go Bus first
    bus_mission = fetch_mission_from_bus(agent)
    if bus_mission:
        return bus_mission

    # Evolutionary mission
    return get_evolutionary_mission(agent, cycle)

def run_agent(agent, mission):
    """Run a single agent via Runtime V5 (LLM)"""
    env = dict(os.environ, VLLM_URL=VLLM_URL)
    agent_name = "adam-" + agent if not agent.startswith("adam-") else agent

    if RUNTIME_V5.exists():
        logger.info(f"Lancement {agent_name} via Runtime V5 (LLM)...")
        try:
            result = subprocess.run(
                ["python3", str(RUNTIME_V5), agent_name, "-m", mission],
                capture_output=True, text=True, timeout=AGENT_TIMEOUT, env=env
            )
            exit_code = result.returncode
            output = result.stdout.strip()
            error = result.stderr.strip()

            # Extract tools created from output
            tools = []
            import re
            for m in re.finditer(r'"tool":\s*"([^"]+)"', output):
                tools.append(m.group(1))

            if exit_code == 0:
                logger.info(f"{agent_name}: OK (LLM) - {output[:100]}")
            else:
                logger.warning(f"{agent_name}: exit={exit_code} - {error[:200]}")

            publish_packet(agent, exit_code, output[:500], "done" if exit_code == 0 else "failed",
                          thought=f"Mission: {mission[:60]}", mission=mission, tools=tools)
            return exit_code

        except subprocess.TimeoutExpired:
            logger.warning(f"{agent_name}: timeout après {AGENT_TIMEOUT}s")
            publish_packet(agent, 124, "", "timeout", thought=f"Timeout: {mission[:60]}", mission=mission)
            return 124
        except Exception as e:
            logger.error(f"{agent_name}: erreur {e}")
            publish_packet(agent, 1, "", "error", thought=f"Erreur: {str(e)[:60]}")
            return 1
    else:
        # Fallback: script classique
        script = BASE / "agents" / agent / f"adam-{agent}.py"
        if not script.exists():
            script = BASE / "agents" / agent / f"{agent}.py"
        if not script.exists():
            script = BASE / "agents" / agent / "watch.py"
        if not script.exists():
            return 0

        logger.info(f"Lancement {agent_name} (script)...")
        try:
            result = subprocess.run(
                ["python3", str(script), "--mission", mission],
                capture_output=True, text=True, timeout=60
            )
            publish_packet(agent, result.returncode, result.stdout[:200], "done" if result.returncode == 0 else "failed",
                          thought=f"Mission: {mission[:60]}", mission=mission)
            return result.returncode
        except:
            publish_packet(agent, 1, "", "error")
            return 1

def run_cycle(cycle):
    """Run one complete cycle of all agents"""
    for agent in AGENTS:
        mission = get_agent_mission(agent, cycle)
        run_agent(agent, mission)

    # Heartbeat
    payload = json.dumps({
        "topic": "adam:heartbeat",
        "source": "daemon",
        "payload": {"cycle": cycle, "agents": len(AGENTS), "timestamp": datetime.now(timezone.utc).isoformat()},
        "priority": 0
    }).encode()
    try:
        req = urllib.request.Request(GO_BUS, data=payload, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=3)
    except:
        pass

    # Daemon tick
    tick = json.dumps({"topic": "adam:daemon:tick", "source": "daemon", "payload": {"cycle": cycle}, "priority": 0}).encode()
    try:
        req = urllib.request.Request(GO_BUS, data=tick, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=3)
    except:
        pass

def main():
    _acquire_lock()
    PID_FILE.write_text(str(os.getpid()))
    logger.info(f"ADAM Daemon V5.1 — PID={os.getpid()} — {len(AGENTS)} agents — timeout={AGENT_TIMEOUT}s")
    logger.info(f"Runtime V5: {RUNTIME_V5} ({'OK' if RUNTIME_V5.exists() else 'NOT FOUND'})")
    logger.info(f"VLLM URL: {VLLM_URL}")
    logger.info(f"Go Bus: {GO_BUS}")
    logger.info(f"Missions: Go Bus → évolutives → défaut")

    cycle = 0
    while True:
        logger.info(f"--- Cycle {cycle} ---")
        run_cycle(cycle)
        cycle += 1
        time.sleep(5)

if __name__ == "__main__":
    main()
