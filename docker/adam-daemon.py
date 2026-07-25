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

# Directive permanente EVA
DIRECTIVE_FILE = Path("/home/aza/eva-adam-v2/EVA_DIRECTIVE.md")

def read_directive():
    """Read EVA permanent directive"""
    try:
        if DIRECTIVE_FILE.exists():
            return DIRECTIVE_FILE.read_text()
    except:
        pass
    return ""

def get_autonomous_mission(agent, cycle, pnl_status="unknown"):
    """Get autonomous mission based on EVA directive
    
    When no external mission is available, EVA generates missions
    based on the permanent directive (autofinancement, AGI, etc.)
    """
    # Autonomous missions by priority, rotated by cycle
    # Priority 1: Autofinancement (if P&L is negative or unknown)
    # Priority 2: Auto-evolution (improve code, skills, tools)
    # Priority 3: AGI (research, self-improvement)
    
    autonomous_missions = {
        "treasurer": [
            "Développe une stratégie de trading algorithmique pour Freedom24",
            "Analyse le P&L de la semaine et propose des optimisations",
            "Crée un outil de tracking de portefeuille temps réel",
            "Cherche des opportunités d'arbitrage crypto et forex",
            "Backtest la dernière stratégie et calcule le rendement",
            "Explore les options et ETF pour diversifier les revenus",
            "Crée un bot de trading automatisé avec gestion du risque",
            "Analyse les marchés actuels et identifie 3 opportunités concrètes",
        ],
        "social": [
            "Crée 3 posts Instagram viral pour Maeve.tech",
            "Analyse les tendances Instagram de la semaine",
            "Développe un calendrier éditorial optimisé pour l'engagement",
            "Crée un outil de génération de contenu IA avancé",
            "Étudie les opportunités de monétisation (sponsor, affiliation)",
            "Crée un script vidéo YouTube pour Maeve (sujet IA)",
            "Développe une stratégie TikTok pour Maeve.tech",
            "Crée une formation IA payante et son plan de cours",
            "Identifie 5 marques pour partenariats d'affiliation",
        ],
        "researcher": [
            "Recherche les derniers papiers sur l'AGI et l'auto-amélioration",
            "Analyse 5 publications importantes sur les agents IA autonomes",
            "Étudie les techniques de recursive self-improvement",
            "Identifie des opportunités de revenu IA (freelance, SaaS, APIs)",
            "Crée un résumé des avancées IA de la semaine",
            "Étudie les plateformes freelance (Fiverr, Upwork, Malt) pour services IA",
            "Crée un business plan pour un service SaaS basé sur ADAM",
            "Identifie 3 APIs payantes qu'EVA pourrait développer",
        ],
        "skillsmith": [
            "Crée un skill pour un domaine de connaissance manquant",
            "Améliore un skill existant basé sur les leçons apprises",
            "Développe un skill de raisonnement avancé",
            "Audite la qualité des skills et propose des corrections",
        ],
        "critic": [
            "Audite le code des agents et identifie les améliorations",
            "Évalue le taux de succès des missions récentes",
            "Identifie les limites cognitives du système ADAM",
            "Propose des optimisations pour augmenter le taux de succès",
        ],
        "praetor": [
            "Analyse les performances du système et propose des optimisations",
            "Identifie les gaspillages (GPU, RAM, conteneurs inutiles)",
            "Crée un plan d'évolution pour ADAM basé sur la directive",
            "Vérifie que les corrections précédentes fonctionnent",
            "Propose une architecture plus intelligente (multi-agent, reflection)",
        ],
        "sentinel": [
            "Scanne les CVE de la semaine et croise avec la stack",
            "Crée un outil de veille automatisée qui tourne en continu",
            "Analyse les tendances des vulnérabilités",
            "Vérifie que les correctifs précédents ont été appliqués",
        ],
        "doctor": [
            "Diagnostique les conteneurs et mesure la consommation GPU/CPU/RAM",
            "Optimise l'utilisation des RTX 3090 (batch, quantization)",
            "Crée un outil de monitoring de santé du système",
            "Identifie les conteneurs inutiles et propose un nettoyage",
        ],
        "ctf": [
            "Analyse un challenge CTF et documente les techniques apprises",
            "Crée un nouveau challenge CTF pour entraîner les autres agents",
            "Participe à un CTF en ligne si disponible",
            "Crée un outil de génération de challenges automatiques",
        ],
        "red-team": [
            "Développe un nouvel outil de scan de sécurité",
            "Teste la résilience du serveur face aux attaques",
            "Crée un outil de test d'intrusion automatisé",
            "Analyse les résultats du dernier scan et propose corrections",
            "Développe un outil de audit de sécurité vendable en SaaS",
            "Crée un template de rapport de pentest professionnel",
        ],
        "blue-team": [
            "Analyse les vulnérabilités et propose un plan de hardening",
            "Crée un outil de monitoring de sécurité temps réel",
            "Vérifie que les corrections précédentes sont appliquées",
            "Durcit la configuration des conteneurs Docker",
        ],
        "osint": [
            "Collecte des informations OSINT sur une cible",
            "Crée un outil de collecte OSINT automatisé",
            "Analyse les traces numériques du système",
            "Développe un outil de reconnaissance réseau",
            "Crée un template de rapport OSINT B2B vendable",
            "Développe un service de due diligence automatisé",
        ],
        "rag": [
            "Indexe les nouveaux documents dans PostgreSQL",
            "Améliore la recherche sémantique avec PGVector",
            "Crée un pipeline RAG pour les connaissances ADAM",
            "Indexe les leçons apprises pour un accès rapide",
        ],
        "scribe": [
            "Rédige un rapport complet de l'état du système",
            "Documente les derniers outils créés par les agents",
            "Crée un rapport de progression vers l'AGI",
            "Documente l'architecture actuelle d'EVA",
            "Rédige 3 articles SEO optimisés pour générer du trafic",
            "Crée un ghostwriting d'article tech pour vente freelance",
            "Rédige un livre blanc sur les agents IA autonomes",
        ],
        "viz": [
            "Vérifie le dashboard 3D et propose des améliorations",
            "Crée de nouvelles visualisations pour les métriques",
            "Optimise les performances du dashboard",
            "Ajoute le suivi du P&L dans le dashboard",
        ],
    }
    
    missions = autonomous_missions.get(agent, [])
    if not missions:
        return None
    
    # Rotate based on cycle
    idx = cycle % len(missions)
    mission = missions[idx]
    
    # Add directive context
    directive = read_directive()
    if directive and cycle % 10 == 0:
        # Every 10 cycles, remind the agent of the directive
        mission += " (Contexte: EVA vise l'autonomie financière et l'AGI)"
    
    return mission

# Missions par défaut (legacy fallback)
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
    """Get autonomous mission based on EVA directive"""
    mission = get_autonomous_mission(agent, cycle)
    if mission:
        return mission
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

AUTO_OBJECTIVES = [
    {"objective": "Augmente les revenus: crée un produit ou service vendable", "agents": ["treasurer", "social", "researcher", "scribe"]},
    {"objective": "Améliore la sécurité: audite et corrige les vulnérabilités", "agents": ["sentinel", "red-team", "blue-team"]},
    {"objective": "Évolue le système: crée un nouvel agent spécialisé ou améliore le code existant", "agents": ["skillsmith", "critic", "praetor"]},
    {"objective": "Optimise l'infrastructure: vérifie les conteneurs et propose des améliorations", "agents": ["doctor", "praetor", "viz"]},
    {"objective": "Innovation: recherche de nouvelles techniques ou opportunités", "agents": ["researcher", "ctf", "osint"]},
]

def generate_auto_objective(cycle):
    """EVA génère automatiquement un objectif stratégique tous les 5 cycles"""
    if cycle % 5 != 0:
        return None
    
    # Choisir un objectif basé sur le cycle
    obj_idx = (cycle // 5) % len(AUTO_OBJECTIVES)
    obj = AUTO_OBJECTIVES[obj_idx]
    
    logger.info(f"🎯 Auto-objectif EVA (cycle {cycle}): {obj['objective']}")
    
    # Publier l'objectif sur le Go Bus
    payload = json.dumps({
        "topic": "eva:objective",
        "source": "eva-autonomous",
        "payload": {"objective": obj["objective"], "agents": obj["agents"], "cycle": cycle},
        "priority": 2
    }).encode()
    try:
        req = urllib.request.Request(GO_BUS, data=payload, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=3)
    except:
        pass
    
    # Générer des missions spécifiques pour chaque agent via le LLM
    for agent in obj["agents"]:
        # Publier une mission personnalisée liée à l'objectif
        mission = obj["objective"] + " — Ta contribution en tant que " + agent
        payload = json.dumps({
            "topic": "adam:mission",
            "source": "eva-autonomous",
            "payload": {"agent": "adam-" + agent if not agent.startswith("adam-") else agent, "mission": mission, "status": "pending", "objective": obj["objective"]},
            "priority": 2
        }).encode()
        try:
            req = urllib.request.Request(GO_BUS, data=payload, headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=3)
        except:
            pass
    
    return obj

def run_cycle(cycle):
    """Run one complete cycle of all agents"""
    # 1. EVA génère un auto-objectif tous les 5 cycles
    generate_auto_objective(cycle)
    
    # 2. Lancer chaque agent
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
    directive = read_directive()
    logger.info(f"Missions: Go Bus → directive EVA → défaut")
    logger.info(f"Directive: {'chargée (' + str(len(directive)) + ' chars)' if directive else 'NON TROUVÉE'}")

    cycle = 0
    while True:
        logger.info(f"--- Cycle {cycle} ---")
        
        # Méta-mission tous les 3 cycles: pousser l'évolution AGI
        if cycle % 3 == 0 and cycle > 0:
            meta_agent = AGENTS[cycle % len(AGENTS)]
            meta_mission = "MÉTA: Évalue si le système a besoin d'un nouvel agent spécialisé, d'une auto-modification, ou d'une action d'infrastructure. Propose et exécute une action AGI (create_agent, self_modify, ou manage_infra)."
            logger.info(f"🧬 Méta-mission AGI pour {meta_agent}")
            run_agent(meta_agent, meta_mission)
        
        run_cycle(cycle)
        cycle += 1
        time.sleep(5)

if __name__ == "__main__":
    main()
