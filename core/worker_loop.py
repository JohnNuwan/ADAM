#!/usr/bin/env python3
"""
EVA ADAM v2 — Worker Sidecar (Levier 4)
=========================================
Worker Dockerisé qui écoute le bus d'événements SQLite,
récupère les événements en attente et exécute les handlers
dans un sous-processus isolé avec timeout.

Usage (conteneur) :
    python3 worker_loop.py

Variables d'environnement :
    WORKER_ID        : Identifiant du worker (défaut: worker-1)
    WORKER_TIMEOUT   : Timeout max par handler en secondes (défaut: 180)
    DB_PATH          : Chemin vers la base SQLite du bus (défaut: /data/event_bus.db)
"""

import logging
import os
import signal
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# ── Importer le bus d'événements depuis le même répertoire ──
sys.path.insert(0, str(Path(__file__).resolve().parent))
from event_bus import EventBus, GoBusClient

# ── Variables d'environnement ──
WORKER_ID = os.environ.get("WORKER_ID", "worker-1")
WORKER_TIMEOUT = int(os.environ.get("WORKER_TIMEOUT", "180"))
DB_PATH = os.environ.get("DB_PATH", "/data/event_bus.db")

# ── Go Bus client (HTTP — privilégié pour la publication) ──
go_bus = GoBusClient()

# ── Chemins internes du conteneur ──
HANDLERS_DIR = Path("/handlers")       # Scripts montés en lecture seule
DATA_DIR = Path("/data")               # Données persistantes (volume partagé)
LOGS_DIR = DATA_DIR / "logs"           # Répertoire des logs du worker

# ── Logging ──
LOGS_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(str(LOGS_DIR / "worker.log")),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(f"eva.adam.worker.{WORKER_ID}")


def resolve_handler(handler_str: str) -> str:
    """
    Résout le chemin du handler pour l'environnement conteneurisé.

    Les souscriptions stockent des chemins comme ~/scripts/cicd-hook.sh
    qui doivent être traduits vers /handlers/cicd-hook.sh dans le conteneur.
    """
    # Remplacer ~/scripts/ par /handlers/ (chemin monté en volume)
    handler_str = handler_str.replace("~/scripts/", "/handlers/")
    # Remplacer ~ par le home du worker (fallback)
    handler_str = handler_str.replace("~", str(Path.home()))
    return handler_str


def get_all_pending_events(db_path: str, limit: int = 50) -> list[dict]:
    """
    Récupère tous les événements en attente, triés par priorité puis ancienneté.

    Args:
        db_path: Chemin vers la base SQLite
        limit:  Nombre maximum d'événements à récupérer

    Returns:
        Liste des événements (dict)
    """
    conn = sqlite3.connect(db_path, timeout=30.0)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """SELECT * FROM events
           WHERE status = 'pending'
           ORDER BY priority DESC, created_at ASC
           LIMIT ?""",
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def run_handler(handler_cmd: str, event: dict, timeout: int) -> dict:
    """
    Exécute un handler dans un sous-processus isolé avec timeout.

    Args:
        handler_cmd: Commande complète du handler (résolue)
        event:       Dictionnaire de l'événement déclencheur
        timeout:     Timeout en secondes

    Returns:
        Dictionnaire avec : exit_code, output, success, duration_ms
    """
    started_at = time.monotonic()
    output = ""
    exit_code = -1
    success = False

    try:
        logger.debug(
            "[%s] Exécution : %s (event #%d, channel=%s)",
            WORKER_ID, handler_cmd, event["id"], event["channel"],
        )

        # Découper la commande pour subprocess
        parts = handler_cmd.split()
        result = subprocess.run(
            parts,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(HANDLERS_DIR),
        )

        output = result.stdout
        if result.stderr:
            output += "\n--- STDERR ---\n" + result.stderr

        exit_code = result.returncode
        success = exit_code == 0

        if success:
            logger.info(
                "[%s] ✅ Handler terminé : %s (event #%d, sortie=%d)",
                WORKER_ID, parts[0], event["id"], exit_code,
            )
        else:
            logger.warning(
                "[%s] ⚠️ Handler échoué : %s (event #%d, sortie=%d)",
                WORKER_ID, parts[0], event["id"], exit_code,
            )

    except subprocess.TimeoutExpired:
        output = f"TIMEOUT après {timeout}s"
        exit_code = -9  # Signal SIGKILL
        success = False
        logger.error(
            "[%s] ⏰ Timeout handler : %s (event #%d, limit=%ds)",
            WORKER_ID, handler_cmd, event["id"], timeout,
        )
    except FileNotFoundError as e:
        output = f"Handler introuvable : {e}"
        exit_code = -1
        success = False
        logger.error(
            "[%s] ❌ Handler introuvable : %s (event #%d)",
            WORKER_ID, handler_cmd, event["id"],
        )
    except Exception as e:
        output = f"Erreur inattendue : {e}"
        exit_code = -1
        success = False
        logger.exception(
            "[%s] ❌ Exception dans le handler : %s (event #%d)",
            WORKER_ID, handler_cmd, event["id"],
        )

    duration_ms = int((time.monotonic() - started_at) * 1000)
    # Tronquer la sortie à 10 Ko pour l'audit trail
    output = output[:10240]

    return {
        "exit_code": exit_code,
        "output": output,
        "success": success,
        "duration_ms": duration_ms,
    }


def worker_loop():
    """
    Boucle principale du worker.

    - Se connecte au bus SQLite partagé via volume
    - Récupère les événements en attente toutes les 5 secondes
    - Réserve (claim) chaque événement atomiquement
    - Exécute les handlers associés dans un sous-processus avec timeout
    - Enregistre le résultat dans l'audit trail
    """
    logger.info("═" * 60)
    logger.info("🚀 Worker ADAM v2 démarré")
    logger.info("   ID          : %s", WORKER_ID)
    logger.info("   Timeout     : %ds", WORKER_TIMEOUT)
    logger.info("   DB Path     : %s", DB_PATH)
    logger.info("   Handlers    : %s", HANDLERS_DIR)
    logger.info("   Logs        : %s", LOGS_DIR / "worker.log")
    logger.info("═" * 60)

    # Vérifier que la base de données existe
    db = Path(DB_PATH)
    if not db.exists():
        logger.warning("Base de données introuvable : %s (attente...)", DB_PATH)

    # Initialiser le bus d'événements
    bus = EventBus(Path(DB_PATH))

    # Enregistrer le worker comme agent dans le bus
    bus.register_agent(
        WORKER_ID,
        f"ADAM Worker {WORKER_ID}",
        config={
            "timeout": WORKER_TIMEOUT,
            "type": "docker-sidecar",
            "access": {"data": "/data", "handlers": "/handlers (read-only)"},
        },
    )

    cycle_count = 0

    while True:
        try:
            cycle_count += 1

            # 1. Envoyer un battement de cœur
            bus.heartbeat(WORKER_ID)
            bus.update_agent_status(WORKER_ID, "running")
            # Go Bus heartbeat (HTTP — privilégié)
            go_bus.publish("adam:heartbeat", {
                "agent_id": WORKER_ID,
                "status": "running",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }, source=WORKER_ID)

            # 2. Récupérer les événements en attente
            pending = get_all_pending_events(DB_PATH)
            if pending:
                logger.info(
                    "[cycle #%d] 📨 %d événement(s) en attente",
                    cycle_count, len(pending),
                )

            # 3. Traiter chaque événement
            for event in pending:
                event_id = event["id"]
                channel = event["channel"]
                payload = event["payload"]

                # Tenter de réserver l'événement (claim atomique)
                if not bus.claim_event(event_id, WORKER_ID):
                    logger.debug(
                        "[cycle #%d] Événement #%d déjà réservé par un autre worker, ignoré",
                        cycle_count, event_id,
                    )
                    continue

                logger.info(
                    "[cycle #%d] 🔄 Traitement event #%d | canal=%s | payload=%s",
                    cycle_count, event_id, channel, payload[:200] if payload else "{}",
                )

                # Récupérer les souscriptions actives pour ce canal
                subscriptions = bus.get_subscriptions(channel)

                if not subscriptions:
                    logger.info(
                        "[cycle #%d] Aucune souscription pour le canal '%s', event #%d marqué 'done'",
                        cycle_count, channel, event_id,
                    )
                    bus.complete_event(event_id, success=True)
                    continue

                # Exécuter chaque handler
                all_success = True
                started_at = datetime.now(timezone.utc).isoformat()

                for sub in subscriptions:
                    handler_raw = sub["handler"]
                    handler_resolved = resolve_handler(handler_raw)

                    logger.info(
                        "[cycle #%d] ▶ Handler : %s → %s",
                        cycle_count, handler_raw, handler_resolved,
                    )

                    # Exécuter dans un sous-processus isolé
                    result = run_handler(handler_resolved, event, WORKER_TIMEOUT)

                    # Enregistrer dans l'audit trail
                    bus.log_execution(
                        agent_id=sub["agent_id"],
                        event_id=event_id,
                        trigger_channel=channel,
                        started_at=started_at,
                        finished_at=datetime.now(timezone.utc).isoformat(),
                        duration_ms=result["duration_ms"],
                        exit_code=result["exit_code"],
                        output=result["output"],
                        success=result["success"],
                    )

                    if not result["success"]:
                        all_success = False

                # Marquer l'événement comme terminé
                bus.complete_event(event_id, success=all_success)
                status_symbol = "✅" if all_success else "⚠️"
                logger.info(
                    "[cycle #%d] %s Event #%d terminé (%d handler(s))",
                    cycle_count, status_symbol, event_id, len(subscriptions),
                )
                # Publier le résultat sur le Go Bus (HTTP — privilégié)
                go_bus.publish(f"worker:done", {
                    "event_id": event_id,
                    "channel": channel,
                    "worker_id": WORKER_ID,
                    "success": all_success,
                    "handlers": len(subscriptions),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }, source=WORKER_ID, priority=1 if not all_success else 0)

            # 4. Pause avant le prochain cycle
            time.sleep(5)

        except KeyboardInterrupt:
            logger.info("🛑 Worker arrêté par signal utilisateur")
            bus.update_agent_status(WORKER_ID, "idle")
            break
        except Exception as e:
            logger.exception(
                "[cycle #%d] ❌ Erreur dans la boucle principale : %s",
                cycle_count, e,
            )
            # Attendre avant de recommencer (évite le spin sur erreur persistante)
            time.sleep(10)


def main():
    """
    Point d'entrée du worker sidecar.
    Gère le signal SIGTERM pour un arrêt gracieux.
    """
    running = True

    def signal_handler(signum, frame):
        nonlocal running
        logger.warning("Signal %s reçu, arrêt gracieux...", signum)
        running = False

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    worker_loop()


if __name__ == "__main__":
    main()
