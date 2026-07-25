#!/usr/bin/env python3
# ═══════════════════════════════════════════════════════════════════════════
# ⚠️  DEPRECATED — Ce daemon SQLite est conservé pour compatibilité descendante.
#     Le Go Event Bus (port 8086) remplace ce daemon pour la gestion des
#     événements. Les nouveaux composants doivent utiliser GoBusClient ou
#     EventBus.publish_http() / EventBus.query_http() depuis event_bus.py.
#     Voir: http://localhost:8086/api/stats
# ═══════════════════════════════════════════════════════════════════════════
"""
EVA ADAM v2 — Daemon d'Orchestration (Event Daemon)  [DEPRECATED]
===================================================================
Levier 1 : Architecture Événementielle

⚠️  DEPRECATED — Utiliser le Go Bus (http://localhost:8086) à la place.
    Ce daemon SQLite reste fonctionnel mais ne devrait plus être utilisé
    pour de nouveaux déploiements.

Daemon principal qui écoute le bus d'événements SQLite, récupère les
événements en attente, et déclenche les handlers des agents ADAM abonnés.

Cycle :
  1. Poll le bus pour les événements pending (toutes les 2s)
  2. Pour chaque événement, trouve les souscriptions actives
  3. Réserve l'événement (claim atomic) pour éviter les races
  4. Exécute le handler (subprocess, timeout, capture stdout/stderr)
  5. Marque l'événement comme done/failed
  6. Log l'exécution dans l'audit trail
  7. Met à jour le statut de l'agent

Lancement :
    python3 event_daemon.py              # foreground
    python3 event_daemon.py --background # daemon (background)
    python3 event_daemon.py --status     # statut
    python3 event_daemon.py --stop       # arrêt propre
"""

import json
import subprocess
import time
import logging
import sys
import os
import signal
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

# Import local
sys.path.insert(0, str(Path(__file__).parent))
from event_bus import EventBus, DB_PATH, CHANNELS

logger = logging.getLogger("eva.adam.daemon")

ADAM_V2_DIR = Path.home() / "eva-adam-v2"
PID_FILE = ADAM_V2_DIR / "event_daemon.pid"
LOG_DIR = ADAM_V2_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

POLL_INTERVAL = 2.0  # secondes
MAX_CONCURRENT = 4   # max handlers simultanés
HANDLER_TIMEOUT_DEFAULT = 180  # secondes


class EventDaemon:
    """Daemon d'orchestration des agents ADAM v2."""

    def __init__(self):
        self.bus = EventBus()
        self.running = False
        self._active_handlers = {}  # event_id -> subprocess.Popen

    def _reap_stale_events(self):
        """Récupère les événements stuck en 'processing' d'un précédent démarrage.

        Quand le daemon redémarre, les events qu'il avait claimés (status='processing')
        ne seront jamais marqués done/failed car les handlers sont morts.
        Cette méthode les marque comme failed avec un message explicite.
        """
        conn = self.bus._get_conn()
        # Sélectionner d'abord (la colonne agent_id n'existe pas dans events)
        rows = conn.execute(
            "SELECT id, channel FROM events WHERE status='processing'"
        ).fetchall()
        if rows:
            conn.execute(
                "UPDATE events SET status='failed' WHERE status='processing'"
            )
            conn.commit()
            for row in rows:
                eid, ch = row
                logger.warning(f"⏱ Event stale récupéré: #{eid} (channel={ch})")
                self.bus.log_execution(
                    agent_id="event-daemon",
                    event_id=eid,
                    trigger_channel=ch,
                    started_at=datetime.now(timezone.utc).isoformat(),
                    finished_at=datetime.now(timezone.utc).isoformat(),
                    duration_ms=0,
                    exit_code=-1,
                    output="Event stale: handler mort après redémarrage daemon",
                    success=False,
                )
        # NE PAS fermer la connexion — elle est thread-local et gérée par _get_conn()

    def start(self):
        """Démarre la boucle principale du daemon."""
        self.running = True
        # Récupère les events stale d'un précédent démarrage
        self._reap_stale_events()
        logger.info("=" * 60)
        logger.info("EVA ADAM v2 — Event Daemon démarré")
        logger.info(f"Bus: {DB_PATH}")
        logger.info(f"Poll interval: {POLL_INTERVAL}s")
        logger.info(f"Max concurrent: {MAX_CONCURRENT}")
        logger.info("=" * 60)

        # Enregistre le signal handler pour arrêt propre
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)

        # Publie un événement de démarrage
        self.bus.publish("adam:heartbeat", {
            "agent_id": "event-daemon",
            "action": "start",
            "pid": os.getpid(),
        }, source="event-daemon")

        while self.running:
            try:
                self._poll_cycle()
                time.sleep(POLL_INTERVAL)
            except Exception as e:
                logger.error(f"Erreur dans le cycle de polling: {e}", exc_info=True)
                time.sleep(POLL_INTERVAL * 2)  # Back-off

        self._shutdown()

    def _poll_cycle(self):
        """Un cycle de polling : récupère et traite les événements pending."""
        # Récupère tous les canaux qui ont des événements en attente ou skipped
        # (skipped = potentiellement re-promotable si une sub a été ajoutée)
        conn = self.bus._get_conn()
        channels = conn.execute(
            """SELECT DISTINCT channel FROM events WHERE status IN ('pending', 'skipped')"""
        ).fetchall()

        if not channels:
            # Pas d'events pending → récolter les handlers terminés quand même
            self._reap_handlers()
            return

        # Vérifie qu'on n'est pas saturé
        if len(self._active_handlers) >= MAX_CONCURRENT:
            self._reap_handlers()
            return

        for (channel,) in channels:
            # Récupère les souscriptions actives pour ce canal
            subs = self.bus.get_subscriptions(channel)
            if not subs:
                # Pas de souscripteur → marquer comme skipped
                self._skip_orphan_events(channel)
                continue

            # Re-promote les events skipped en pending si une souscription existe maintenant
            self._promote_skipped_events(channel)

            # Récupère les événements pending
            events = self.bus.get_pending_events(channel, limit=MAX_CONCURRENT)
            for event in events:
                if len(self._active_handlers) >= MAX_CONCURRENT:
                    break

                # Tente de réserver l'événement (atomic)
                if not self.bus.claim_event(event["id"], "event-daemon"):
                    continue  # Déjà pris par un autre thread

                # Dispatch vers chaque souscripteur
                for sub in subs:
                    self._dispatch(event, sub)

        # Nettoie les handlers terminés
        self._reap_handlers()

    def _dispatch(self, event: dict, subscription: dict):
        """
        Déclenche le handler d'un agent pour un événement donné.
        Exécute le handler en subprocess avec timeout.
        """
        agent_id = subscription["agent_id"]
        handler = subscription["handler"]
        event_id = event["id"]
        channel = event["channel"]

        # Vérifie l'existence du script handler (exit=127 si manquant)
        # Format typique: "bash ~/scripts/xxx.sh" ou "python3 ~/scripts/xxx.py"
        # On ignore l'interpréteur (1er token) et on cherche le fichier script
        handler_path = ""
        if handler:
            parts = handler.split()
            for part in parts[1:]:  # skip bash/python3/etc.
                candidate = os.path.expanduser(part)
                if os.path.isfile(candidate):
                    handler_path = candidate
                    break
            if not handler_path:
                # Aucun fichier trouvé → utilise le 1er token comme fallback
                handler_path = parts[0] if parts else ""
        if handler_path and not os.path.isfile(handler_path):
            now_iso = datetime.now(timezone.utc).isoformat()
            logger.error(f"✗ Handler introuvable pour {agent_id}: {handler_path}")
            self.bus.complete_event(event_id, success=False)
            self.bus.log_execution(
                agent_id=agent_id,
                event_id=event_id,
                trigger_channel=channel,
                started_at=now_iso,
                finished_at=now_iso,
                exit_code=127,
                output=f"Handler introuvable: {handler_path}",
                success=False,
            )
            self.bus.update_agent_status(
                agent_id, "error", last_status="error",
                last_error=f"handler introuvable: {handler_path}",
            )
            self.bus.publish("adam:error", {
                "agent_id": agent_id,
                "event_id": event_id,
                "exit_code": 127,
                "error": f"handler introuvable: {handler_path}",
            }, source="event-daemon")
            return

        # Parse le payload
        try:
            payload = json.loads(event["payload"])
        except (json.JSONDecodeError, TypeError):
            payload = {}

        # Prépare les variables d'environnement pour le handler
        env = os.environ.copy()
        env["ADAM_EVENT_ID"] = str(event_id)
        env["ADAM_EVENT_CHANNEL"] = channel
        env["ADAM_EVENT_SOURCE"] = event["source"]
        env["ADAM_EVENT_PAYLOAD"] = json.dumps(payload, ensure_ascii=False)
        env["ADAM_EVENT_PRIORITY"] = str(event["priority"])
        env["ADAM_AGENT_ID"] = agent_id
        env["ADAM_V2_DIR"] = str(ADAM_V2_DIR)

        # Récupère la config de l'agent (timeout)
        agent_info = self.bus.get_agent_status(agent_id)
        timeout = HANDLER_TIMEOUT_DEFAULT
        if agent_info and agent_info.get("config"):
            try:
                config = json.loads(agent_info["config"])
                timeout = config.get("timeout", HANDLER_TIMEOUT_DEFAULT)
            except (json.JSONDecodeError, TypeError):
                pass

        started_at = datetime.now(timezone.utc).isoformat()
        logger.info(f"Dispatch: {agent_id} ← {channel} (event #{event_id}, timeout={timeout}s)")

        # Met à jour le statut de l'agent
        self.bus.update_agent_status(agent_id, "running", pid=os.getpid())

        try:
            proc = subprocess.Popen(
                handler,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                text=True,
            )

            # Enregistre dans les handlers actifs
            self._active_handlers[event_id] = {
                "proc": proc,
                "agent_id": agent_id,
                "event_id": event_id,
                "channel": channel,
                "handler": handler,
                "started_at": started_at,
                "timeout": timeout,
            }

        except Exception as e:
            logger.error(f"Échec de lancement du handler {handler}: {e}")
            self.bus.complete_event(event_id, success=False)
            self.bus.log_execution(
                agent_id=agent_id,
                event_id=event_id,
                trigger_channel=channel,
                started_at=started_at,
                finished_at=datetime.now(timezone.utc).isoformat(),
                exit_code=-1,
                output=str(e),
                success=False,
            )
            self.bus.update_agent_status(agent_id, "error", last_status="error", last_error=str(e))
            # Publie un événement d'erreur
            self.bus.publish("adam:error", {
                "agent_id": agent_id,
                "event_id": event_id,
                "error": str(e),
            }, source=agent_id)

    def _reap_handlers(self):
        """Vérifie les handlers terminés et met à jour le bus."""
        finished = []

        for event_id, info in list(self._active_handlers.items()):
            proc = info["proc"]
            ret = proc.poll()
            agent_id = info["agent_id"]
            channel = info["channel"]

            if ret is not None:
                # Le handler est terminé
                finished.append(event_id)
                success = (ret == 0)
                now = datetime.now(timezone.utc).isoformat()

                # Calcule la durée
                started = info["started_at"]
                try:
                    started_dt = datetime.fromisoformat(started)
                    now_dt = datetime.fromisoformat(now)
                    duration_ms = int((now_dt - started_dt).total_seconds() * 1000)
                except Exception:
                    duration_ms = None

                # Capture stdout/stderr
                stdout, stderr = proc.communicate()
                output = (stdout or "") + (stderr or "")
                if len(output) > 4096:
                    output = output[:4096] + "\n...[tronqué]..."

                # Log l'exécution
                self.bus.log_execution(
                    agent_id=agent_id,
                    event_id=event_id,
                    trigger_channel=channel,
                    started_at=started,
                    finished_at=now,
                    duration_ms=duration_ms,
                    exit_code=ret,
                    output=output,
                    success=success,
                )

                # Marque l'événement
                self.bus.complete_event(event_id, success=success)

                # Met à jour le statut de l'agent
                if success:
                    self.bus.update_agent_status(agent_id, "idle", last_status="ok")
                    logger.info(f"✓ {agent_id} terminé (event #{event_id}, exit={ret}, {duration_ms}ms)")
                    # Publie un heartbeat
                    self.bus.publish("adam:heartbeat", {
                        "agent_id": agent_id,
                        "event_id": event_id,
                        "status": "ok",
                        "duration_ms": duration_ms,
                    }, source=agent_id)
                else:
                    self.bus.update_agent_status(
                        agent_id, "error", last_status="error",
                        last_error=f"exit code {ret}: {output[:200]}",
                    )
                    logger.warning(f"✗ {agent_id} échoué (event #{event_id}, exit={ret})")
                    self.bus.publish("adam:error", {
                        "agent_id": agent_id,
                        "event_id": event_id,
                        "exit_code": ret,
                        "output": output[:500],
                    }, source=agent_id)

            elif (datetime.now(timezone.utc) - datetime.fromisoformat(info["started_at"])).total_seconds() > info["timeout"]:
                # Timeout — tue le handler
                logger.warning(f"⏱ Timeout {agent_id} (event #{event_id}, {info['timeout']}s)")
                proc.kill()
                proc.wait()
                finished.append(event_id)
                self.bus.complete_event(event_id, success=False)
                self.bus.log_execution(
                    agent_id=agent_id,
                    event_id=event_id,
                    trigger_channel=channel,
                    started_at=info["started_at"],
                    finished_at=datetime.now(timezone.utc).isoformat(),
                    exit_code=-1,
                    output=f"Timeout après {info['timeout']}s",
                    success=False,
                )
                self.bus.update_agent_status(
                    agent_id, "error", last_status="error",
                    last_error=f"timeout après {info['timeout']}s",
                )
                self.bus.publish("adam:error", {
                    "agent_id": agent_id,
                    "event_id": event_id,
                    "error": "timeout",
                    "timeout_s": info["timeout"],
                }, source="event-daemon")

        # Nettoie
        for eid in finished:
            del self._active_handlers[eid]

    def _skip_orphan_events(self, channel: str):
        """Marque les événements sans souscripteur comme 'skipped'."""
        conn = self.bus._get_conn()
        conn.execute(
            "UPDATE events SET status='skipped' WHERE channel=? AND status='pending'",
            (channel,),
        )
        conn.commit()

    def _promote_skipped_events(self, channel: str):
        """Re-promote les events 'skipped' en 'pending' si une souscription existe maintenant.

        Corrige le bug où un event publié avant l'ajout d'une souscription
        restait bloqué en 'skipped' à jamais.
        """
        conn = self.bus._get_conn()
        conn.execute(
            "UPDATE events SET status='pending' WHERE channel=? AND status='skipped'",
            (channel,),
        )
        conn.commit()

    def _signal_handler(self, signum, frame):
        """Gère SIGTERM/SIGINT pour un arrêt propre."""
        logger.info(f"Signal {signum} reçu — arrêt en cours...")
        self.running = False

    def _shutdown(self):
        """Arrêt propre du daemon."""
        logger.info("Arrêt du daemon — nettoyage des handlers actifs...")

        # Attend les handlers en cours (max 30s)
        deadline = time.time() + 30
        while self._active_handlers and time.time() < deadline:
            self._reap_handlers()
            if self._active_handlers:
                time.sleep(1)

        # Tue les handlers restants
        for event_id, info in self._active_handlers.items():
            info["proc"].kill()
            self.bus.complete_event(event_id, success=False)
            logger.warning(f"Handler tué: {info['agent_id']} (event #{event_id})")

        # Publie l'événement d'arrêt
        self.bus.publish("adam:heartbeat", {
            "agent_id": "event-daemon",
            "action": "stop",
        }, source="event-daemon")

        self.bus.close()
        logger.info("Daemon arrêté.")


def daemonize():
    """Passe en mode daemon (background)."""
    pid = os.fork()
    if pid > 0:
        # Parent — exit
        print(f"Daemon démarré (PID: {pid})")
        PID_FILE.write_text(str(pid))
        return

    # Enfant — devient daemon
    os.setsid()
    # Deuxième fork (évite de reacquerir un terminal)
    pid = os.fork()
    if pid > 0:
        os._exit(0)

    # Redirige stdio vers /dev/null
    sys.stdin = open("/dev/null", "r")
    sys.stdout = open(LOG_DIR / "daemon.log", "a")
    sys.stderr = sys.stdout

    # Écrit le PID
    PID_FILE.write_text(str(os.getpid()))

    # Démarre le daemon
    daemon = EventDaemon()
    daemon.start()


def stop_daemon():
    """Arrête le daemon en cours."""
    if not PID_FILE.exists():
        print("Aucun daemon en cours (pas de PID file)")
        return

    pid = int(PID_FILE.read_text().strip())
    try:
        os.kill(pid, signal.SIGTERM)
        print(f"Signal SIGTERM envoyé au daemon (PID: {pid})")
        # Attend que le PID file soit supprimé
        for _ in range(10):
            if not PID_FILE.exists():
                break
            time.sleep(1)
        if PID_FILE.exists():
            print("Le daemon ne s'est pas arrêté — SIGKILL")
            os.kill(pid, signal.SIGKILL)
        PID_FILE.unlink(missing_ok=True)
    except ProcessLookupError:
        print(f"Processus {pid} introuvable — nettoyage du PID file")
        PID_FILE.unlink(missing_ok=True)


def status_daemon():
    """Affiche le statut du daemon."""
    if PID_FILE.exists():
        pid = int(PID_FILE.read_text().strip())
        try:
            os.kill(pid, 0)  # Check si le process existe
            print(f"✓ Daemon en cours (PID: {pid})")
        except ProcessLookupError:
            print(f"✗ PID file existe mais processus {pid} mort")
            PID_FILE.unlink(missing_ok=True)
    else:
        print("✗ Daemon non démarré")

    # Stats du bus
    bus = EventBus()
    stats = bus.get_stats()
    print(f"\nStatistiques du bus:")
    print(f"  Total événements: {stats['total_events']}")
    print(f"  En attente: {stats['pending']}")
    print(f"  En cours: {stats['processing']}")
    print(f"  Terminés: {stats['done']}")
    print(f"  Échoués: {stats['failed']}")

    agents = bus.get_all_agents()
    print(f"\nAgents ({len(agents)}):")
    for a in agents:
        hb = a.get('heartbeat_at')
        hb_str = hb[:19] if hb else '-'
        print(f"  {a['agent_id']:20s} | {a['status']:10s} | last: {a.get('last_status', '-')} | hb: {hb_str}")

    bus.close()


if __name__ == "__main__":
    # FileHandler toujours, StreamHandler seulement en mode foreground (start)
    _handlers = [logging.FileHandler(LOG_DIR / "daemon.log")]
    if len(sys.argv) >= 2 and sys.argv[1] == "start":
        _handlers.append(logging.StreamHandler())
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=_handlers,
    )

    if len(sys.argv) < 2:
        print("Usage: event_daemon.py [start|start-bg|status|stop]")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "start":
        daemon = EventDaemon()
        daemon.start()

    elif cmd == "start-bg":
        daemonize()

    elif cmd == "stop":
        stop_daemon()

    elif cmd == "status":
        status_daemon()

    elif cmd == "restart":
        stop_daemon()
        time.sleep(2)
        daemonize()

    else:
        print(f"Commande inconnue: {cmd}")
        sys.exit(1)