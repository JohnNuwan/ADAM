#!/usr/bin/env python3
"""
EVA ADAM v2 — Bus d'Événements (Event Bus)
==========================================
Levier 1 : Architecture Événementielle (Event-Driven)

Bus d'événements basé sur SQLite (mode WAL) avec Pub/Sub.
Remplace le mode planifié (Cron) par une architecture réactive.

Usage :
    from event_bus import EventBus
    bus = EventBus()
    bus.publish("file:changed", {"path": "/home/aza/script.py", "event": "modify"})
    bus.subscribe("file:changed", callback_fn)
    bus.listen()  # Boucle d'écoute (daemon)
"""

import sqlite3
import json
import threading
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Callable, Optional

logger = logging.getLogger("eva.adam.eventbus")

# --- Constantes ---
ADAM_V2_DIR = Path.home() / "eva-adam-v2"
DB_PATH = ADAM_V2_DIR / "event_bus.db"

# Canaux d'événements (convention namespace:action)
CHANNELS = {
    "file:changed": "Fichier modifié (watcher inotify)",
    "file:created": "Fichier créé",
    "file:deleted": "Fichier supprimé",
    "git:push": "Push Git détecté",
    "git:commit": "Commit Git détecté",
    "git:pull": "Pull Git — synchronisation depuis le distant",
    "security:vulnerability_detected": "Vulnérabilité détectée par ADAM-RED",
    "security:permission_drift": "Dérive de permissions détectée",
    "security:suid_change": "Changement SUID détecté",
    "hardware:gpu_alert": "Alerte GPU (temp, VRAM, utilisation)",
    "hardware:ram_alert": "Alerte RAM (utilisation élevée)",
    "hardware:disk_alert": "Alerte disque (espace critique)",
    "hardware:cpu_alert": "Alerte CPU (surcharge)",
    "service:down": "Service conteneurisé arrêté",
    "service:unhealthy": "Service conteneurisé unhealthy",
    "service:restarted": "Service redémarré (par ADAM-DEPLOY)",
    "dashboard:down": "Dashboard injoignable (HTTP non-200)",
    "dashboard:slow": "Dashboard lent (latence > seuil)",
    "adam:error": "Un ADAM a signalé une erreur",
    "adam:recovered": "Un ADAM s'est rétabli",
    "adam:heartbeat": "Battement de cœur d'un ADAM",
    "cron:missed": "Un cron job a manqué son exécution",
    "config:changed": "Configuration EVA modifiée",
    "skill:created": "Nouvelle compétence créée",
    "skill:updated": "Compétence mise à jour",
    "skill:broken": "Compétence cassée (syntaxe/structure)",
    "test:failed": "Test automatisé échoué",
    "test:passed": "Tests passés avec succès",
    "evolution:code_review": "Analyse de code par adam-evolution (optimisation, factorisation, dead code)",
    "backup:done": "Sauvegarde terminée",
    "backup:failed": "Sauvegarde échouée",
    "osint:finding": "Résultat OSINT intéressant",
    "osint:alert": "Alerte OSINT (menace détectée)",
    "security:scan": "Scan de sécurité demandé",
    "security:alert": "Alerte sécurité générale",
    "monitor:alert": "Alerte monitoring générale",
    "wiki:update": "Mise à jour wiki/documentation",
    "backup:requested": "Sauvegarde demandée",
    "backup:retry": "Re-tentative de sauvegarde",
    # ─── Canaux Phase 3: Architect + Scribe ───
    "architecture:request": "Demande de conception d'architecture",
    "architecture:proposal": "Proposition d'architecture par adam-architect",
    "content:request": "Demande de rédaction de contenu",
    "content:ready": "Contenu prêt par adam-scribe",
    # ─── Canaux Phase 4: Treasurer ───
    "finance:report": "Rapport financier de adam-treasurer",
    "finance:alert": "Alerte budget dépassé",
    # ─── Canaux Phase 5: Researcher ───
    "research:finding": "Résultat de veille scientifique",
    "research:opportunity": "Opportunité économique identifiée (brevet/startup)",
    # ─── Canaux Phase 6: Social ───
    "social:scheduled": "Contenu social planifié",
    "social:engagement": "Métriques d'engagement réseaux sociaux",
    "social:monetization": "Revenu/opportunité de monétisation sociale",
    "update:available": "Mise à jour disponible (système/paquet)",
}

# --- Schéma SQL ---
SCHEMA_SQL = """
-- Table principale des événements
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel TEXT NOT NULL,          -- Canal (ex: "file:changed")
    source TEXT NOT NULL,           -- Source émettrice (ex: "watcher", "adam-red")
    payload TEXT NOT NULL,           -- JSON sérialisé
    priority INTEGER DEFAULT 0,     -- 0=normal, 1=urgent, 2=critique
    created_at TEXT NOT NULL,        -- ISO 8601 UTC
    processed_at TEXT,               -- NULL tant que non traité
    status TEXT DEFAULT 'pending'   -- pending, processing, done, failed, skipped
);

-- Index pour la recherche par canal + statut
CREATE INDEX IF NOT EXISTS idx_events_channel_status ON events(channel, status);
CREATE INDEX IF NOT EXISTS idx_events_status ON events(status);
CREATE INDEX IF NOT EXISTS idx_events_created ON events(created_at DESC);

-- Table des souscriptions (quels ADAM écoutent quels canaux)
CREATE TABLE IF NOT EXISTS subscriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id TEXT NOT NULL,          -- Identifiant ADAM (ex: "adam-blue")
    channel TEXT NOT NULL,           -- Canal écouté
    handler TEXT NOT NULL,           -- Script/handler à exécuter
    enabled INTEGER DEFAULT 1,       -- 1=actif, 0=désactivé
    created_at TEXT NOT NULL,
    UNIQUE(agent_id, channel)
);

-- Table de l'état des agents ADAM
CREATE TABLE IF NOT EXISTS agents (
    agent_id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    status TEXT DEFAULT 'idle',      -- idle, running, error, paused
    last_run_at TEXT,
    last_status TEXT,                -- ok, error, warning
    last_error TEXT,
    pid INTEGER,                     -- PID si en cours d'exécution
    heartbeat_at TEXT,               -- Dernier battement de cœur
    config TEXT DEFAULT '{}'         -- JSON: {timeout, retries, privileges, ...}
);

-- Table de l'historique d'exécution (audit trail)
CREATE TABLE IF NOT EXISTS execution_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id TEXT NOT NULL,
    event_id INTEGER NOT NULL,
    trigger_channel TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    duration_ms INTEGER,
    exit_code INTEGER,
    output TEXT,                     -- stdout/stderr (tronqué)
    success INTEGER DEFAULT 0,       -- 1=succès, 0=échec
    FOREIGN KEY (event_id) REFERENCES events(id),
    FOREIGN KEY (agent_id) REFERENCES agents(agent_id)
);
"""


class EventBus:
    """Bus d'événements SQLite avec Pub/Sub."""

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        """Connexion thread-local avec WAL activé."""
        if not hasattr(self._local, "conn"):
            conn = sqlite3.connect(str(self.db_path), timeout=30.0)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA busy_timeout=5000")
            self._local.conn = conn
        return self._local.conn

    def _init_db(self):
        """Initialise le schéma SQLite."""
        conn = self._get_conn()
        conn.executescript(SCHEMA_SQL)
        conn.commit()
        logger.info(f"Event Bus initialisé: {self.db_path}")

    # --- Publication ---

    def publish(
        self,
        channel: str,
        payload: dict,
        source: str = "system",
        priority: int = 0,
    ) -> int:
        """
        Publie un événement sur le bus.

        Args:
            channel: Canal cible (ex: "file:changed")
            payload: Données de l'événement (sera sérialisé en JSON)
            source: Source émettrice (ex: "watcher", "adam-red")
            priority: 0=normal, 1=urgent, 2=critique

        Returns:
            ID de l'événement créé
        """
        if channel not in CHANNELS:
            logger.warning(f"Canal inconnu: {channel} (publication quand même)")

        now = datetime.now(timezone.utc).isoformat()
        conn = self._get_conn()
        cursor = conn.execute(
            """INSERT INTO events (channel, source, payload, priority, created_at, status)
               VALUES (?, ?, ?, ?, ?, 'pending')""",
            (channel, source, json.dumps(payload, ensure_ascii=False), priority, now),
        )
        conn.commit()
        event_id = cursor.lastrowid
        logger.debug(f"Événement #{event_id} publié: {channel} depuis {source}")
        return event_id

    # --- Souscription ---

    def subscribe(
        self,
        agent_id: str,
        channel: str,
        handler: str,
        enabled: bool = True,
    ) -> int:
        """
        Enregistre une souscription d'un ADAM à un canal.

        Args:
            agent_id: Identifiant de l'ADAM (ex: "adam-blue")
            channel: Canal à écouter
            handler: Script à exécuter quand l'événement arrive
            enabled: Activer la souscription

        Returns:
            ID de la souscription
        """
        now = datetime.now(timezone.utc).isoformat()
        conn = self._get_conn()
        cursor = conn.execute(
            """INSERT INTO subscriptions (agent_id, channel, handler, enabled, created_at)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(agent_id, channel) DO UPDATE SET handler=excluded.handler, enabled=excluded.enabled""",
            (agent_id, channel, handler, 1 if enabled else 0, now),
        )
        conn.commit()
        logger.info(f"Souscription: {agent_id} → {channel} (handler: {handler})")
        return cursor.lastrowid

    def unsubscribe(self, agent_id: str, channel: str):
        """Désactive la souscription d'un ADAM à un canal."""
        conn = self._get_conn()
        conn.execute(
            "UPDATE subscriptions SET enabled=0 WHERE agent_id=? AND channel=?",
            (agent_id, channel),
        )
        conn.commit()
        logger.info(f"Désouscription: {agent_id} ↛ {channel}")

    def get_subscriptions(self, channel: str) -> list[dict]:
        """Retourne toutes les souscriptions actives pour un canal."""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM subscriptions WHERE channel=? AND enabled=1",
            (channel,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_pending_events(self, channel: str, limit: int = 10) -> list[dict]:
        """Retourne les événements en attente pour un canal."""
        conn = self._get_conn()
        rows = conn.execute(
            """SELECT * FROM events
               WHERE channel=? AND status='pending'
               ORDER BY priority DESC, created_at ASC
               LIMIT ?""",
            (channel, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def claim_event(self, event_id: int, agent_id: str) -> bool:
        """
        Réserve un événement pour traitement (atomic, évite les races).
        Retourne True si l'event a été réservé avec succès.
        """
        conn = self._get_conn()
        cursor = conn.execute(
            """UPDATE events SET status='processing', processed_at=?
               WHERE id=? AND status='pending'""",
            (datetime.now(timezone.utc).isoformat(), event_id),
        )
        conn.commit()
        return cursor.rowcount > 0

    def complete_event(self, event_id: int, success: bool = True):
        """Marque un événement comme traité (succès ou échec)."""
        status = "done" if success else "failed"
        conn = self._get_conn()
        conn.execute(
            "UPDATE events SET status=? WHERE id=?",
            (status, event_id),
        )
        conn.commit()

    def log_execution(
        self,
        agent_id: str,
        event_id: int,
        trigger_channel: str,
        started_at: str,
        finished_at: Optional[str] = None,
        duration_ms: Optional[int] = None,
        exit_code: Optional[int] = None,
        output: Optional[str] = None,
        success: bool = False,
    ):
        """Enregistre une exécution dans l'audit trail."""
        conn = self._get_conn()
        conn.execute(
            """INSERT INTO execution_log
               (agent_id, event_id, trigger_channel, started_at, finished_at,
                duration_ms, exit_code, output, success)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                agent_id, event_id, trigger_channel, started_at, finished_at,
                duration_ms, exit_code, output, 1 if success else 0,
            ),
        )
        conn.commit()

    # --- Gestion des agents ---

    def register_agent(
        self,
        agent_id: str,
        display_name: str,
        config: Optional[dict] = None,
    ):
        """Enregistre ou met à jour un agent ADAM."""
        now = datetime.now(timezone.utc).isoformat()
        conn = self._get_conn()
        conn.execute(
            """INSERT INTO agents (agent_id, display_name, status, heartbeat_at, config)
               VALUES (?, ?, 'idle', ?, ?)
               ON CONFLICT(agent_id) DO UPDATE SET
                   display_name=excluded.display_name,
                   config=excluded.config""",
            (agent_id, display_name, now, json.dumps(config or {}, ensure_ascii=False)),
        )
        conn.commit()
        logger.info(f"Agent enregistré: {agent_id} ({display_name})")

    def update_agent_status(
        self,
        agent_id: str,
        status: str,
        last_status: Optional[str] = None,
        last_error: Optional[str] = None,
        pid: Optional[int] = None,
    ):
        """Met à jour le statut d'un agent."""
        now = datetime.now(timezone.utc).isoformat()
        conn = self._get_conn()
        updates = ["status=?", "last_run_at=?"]
        params = [status, now]

        if last_status is not None:
            updates.append("last_status=?")
            params.append(last_status)
        if last_error is not None:
            updates.append("last_error=?")
            params.append(last_error)
        if pid is not None:
            updates.append("pid=?")
            params.append(pid)
        if status == "running":
            updates.append("heartbeat_at=?")
            params.append(now)

        params.append(agent_id)
        conn.execute(
            f"UPDATE agents SET {', '.join(updates)} WHERE agent_id=?",
            params,
        )
        conn.commit()

    def heartbeat(self, agent_id: str):
        """Enregistre un battement de cœur d'un agent."""
        now = datetime.now(timezone.utc).isoformat()
        conn = self._get_conn()
        conn.execute(
            "UPDATE agents SET heartbeat_at=? WHERE agent_id=?",
            (now, agent_id),
        )
        conn.commit()

    def get_agent_status(self, agent_id: str) -> Optional[dict]:
        """Retourne le statut d'un agent."""
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM agents WHERE agent_id=?",
            (agent_id,),
        ).fetchone()
        return dict(row) if row else None

    def get_all_agents(self) -> list[dict]:
        """Retourne tous les agents enregistrés."""
        conn = self._get_conn()
        rows = conn.execute("SELECT * FROM agents ORDER BY agent_id").fetchall()
        return [dict(r) for r in rows]

    # --- Statistiques ---

    def get_stats(self) -> dict:
        """Retourne des statistiques sur le bus d'événements."""
        conn = self._get_conn()
        total = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        pending = conn.execute("SELECT COUNT(*) FROM events WHERE status='pending'").fetchone()[0]
        done = conn.execute("SELECT COUNT(*) FROM events WHERE status='done'").fetchone()[0]
        failed = conn.execute("SELECT COUNT(*) FROM events WHERE status='failed'").fetchone()[0]
        processing = conn.execute("SELECT COUNT(*) FROM events WHERE status='processing'").fetchone()[0]

        # Événements par canal (top 10)
        by_channel = conn.execute(
            """SELECT channel, COUNT(*) as cnt FROM events
               GROUP BY channel ORDER BY cnt DESC LIMIT 10"""
        ).fetchall()

        # Agents actifs
        agents = conn.execute(
            "SELECT COUNT(*) FROM agents WHERE status='running'"
        ).fetchone()[0]

        return {
            "total_events": total,
            "pending": pending,
            "processing": processing,
            "done": done,
            "failed": failed,
            "active_agents": agents,
            "top_channels": [{"channel": r[0], "count": r[1]} for r in by_channel],
        }

    def cleanup_old_events(self, days: int = 30):
        """Nettoie les événements de plus de N jours (done/failed)."""
        conn = self._get_conn()
        conn.execute(
            """DELETE FROM events
               WHERE status IN ('done', 'failed', 'skipped')
               AND created_at < datetime('now', ?)""",
            (f"-{days} days",),
        )
        conn.commit()

    def close(self):
        """Ferme la connexion."""
        if hasattr(self._local, "conn"):
            self._local.conn.close()
            del self._local.conn


# --- Souscriptions par défaut (mapping ADAM → canaux) ---
DEFAULT_SUBSCRIPTIONS = [
    # ADAM-CICD : se déclenche sur file:changed (.py) et git:push
    ("adam-cicd", "file:changed", "bash ~/scripts/cicd-hook.sh"),
    ("adam-cicd", "git:push", "bash ~/scripts/cicd-hook.sh"),
    ("adam-cicd", "git:pull", "bash ~/scripts/cicd-hook.sh"),
    ("adam-cicd", "test:failed", "bash ~/scripts/cicd-hook.sh"),
    # ADAM-ARCHITECT : conçoit architectures, propose des refactors
    ("adam-architect", "architecture:request", "bash ~/scripts/architect-design.sh"),
    ("adam-architect", "evolution:code_review", "bash ~/scripts/architect-design.sh"),
    ("adam-architect", "skill:created", "bash ~/scripts/architect-design.sh"),
    # ADAM-SCRIBE : rédaction de contenu, docs, archivage propositions
    ("adam-scribe", "content:request", "bash ~/scripts/scribe-write.sh"),
    ("adam-scribe", "architecture:proposal", "bash ~/scripts/scribe-write.sh"),
    ("adam-scribe", "skill:updated", "bash ~/scripts/scribe-write.sh"),
    # ADAM-TREASURER : suivi financier, budgets, rentabilité
    ("adam-treasurer", "finance:report", "python3 ~/scripts/treasurer-track.py --event finance:report '{}'"),
    ("adam-treasurer", "finance:alert", "python3 ~/scripts/treasurer-track.py --event finance:alert '{}'"),
    ("adam-treasurer", "evolution:code_review", "python3 ~/scripts/treasurer-track.py --event evolution:code_review '{}'"),
    # ADAM-CRITIC : auto-fix unused imports + tasks de refactor
    ("adam-critic", "evolution:code_review", "python3 ~/scripts/critic-review.py --event evolution:code_review '{}'"),
    # ADAM-RESEARCHER : veille scientifique biomédicale & pharma
    ("adam-researcher", "research:finding", "python3 ~/scripts/researcher-scan.py --event research:finding '{}'"),
    ("adam-researcher", "research:opportunity", "python3 ~/scripts/researcher-scan.py --event research:opportunity '{}'"),
    ("adam-researcher", "osint:finding", "python3 ~/scripts/researcher-scan.py --event osint:finding '{}'"),
    # ADAM-SOCIAL : influence virtuelle & monétisation
    ("adam-social", "content:ready", "python3 ~/scripts/social-manage.py --event content:ready '{}'"),
    ("adam-social", "social:scheduled", "python3 ~/scripts/social-manage.py --event social:scheduled '{}'"),
    ("adam-social", "social:engagement", "python3 ~/scripts/social-manage.py --event social:engagement '{}'"),
    ("adam-social", "social:monetization", "python3 ~/scripts/social-manage.py --event social:monetization '{}'"),
    ("adam-social", "finance:report", "python3 ~/scripts/social-manage.py --event finance:report '{}'"),
    # ADAM-BLUE : se déclenche sur alertes de sécurité
    ("adam-blue", "security:vulnerability_detected", "bash ~/scripts/blue-watch.sh --fix"),
    ("adam-blue", "security:permission_drift", "bash ~/scripts/blue-watch.sh --fix"),
    ("adam-blue", "security:suid_change", "bash ~/scripts/blue-watch.sh --fix"),
    # ADAM-MONITOR : se déclenche sur alertes hardware/service
    ("adam-monitor", "hardware:gpu_alert", "bash ~/scripts/monitor-alert.sh"),
    ("adam-monitor", "hardware:ram_alert", "bash ~/scripts/monitor-alert.sh"),
    ("adam-monitor", "hardware:disk_alert", "bash ~/scripts/monitor-alert.sh"),
    ("adam-monitor", "service:down", "bash ~/scripts/monitor-alert.sh"),
    ("adam-monitor", "service:unhealthy", "bash ~/scripts/monitor-alert.sh"),
    # ADAM-VIZ-CHECKER : se déclenche sur dashboard:down
    ("adam-viz-checker", "dashboard:down", "python3 ~/scripts/viz-checker.py"),
    ("adam-viz-checker", "dashboard:slow", "python3 ~/scripts/viz-checker.py"),
    # ADAM-DOCTOR : se déclenche sur adam:error
    ("adam-doctor", "adam:error", "python3 ~/scripts/doctor-watch.py"),
    ("adam-doctor", "service:restarted", "python3 ~/scripts/doctor-watch.py --verify"),
    # ADAM-PRAETOR : se déclenche sur config:changed et cron:missed
    ("adam-praetor", "config:changed", "bash ~/scripts/praetor-watch.sh"),
    ("adam-praetor", "cron:missed", "bash ~/scripts/praetor-watch.sh"),
    # ADAM-CRITIC : se déclenche sur skill:created/updated/broken
    ("adam-critic", "skill:created", "bash ~/scripts/critic-review.sh"),
    ("adam-critic", "skill:updated", "bash ~/scripts/critic-review.sh"),
    ("adam-critic", "skill:broken", "bash ~/scripts/critic-review.sh --fix"),
    # ADAM-DEPLOY : se déclenche sur service:down pour redémarrer
    ("adam-deploy", "service:down", "bash ~/scripts/deploy.sh --restart"),
    ("adam-deploy", "hardware:disk_alert", "bash ~/scripts/deploy.sh --cleanup"),
    # ADAM-SENTINEL : se déclenche sur update:available et osint:finding
    ("adam-sentinel", "update:available", "bash ~/scripts/sentinel-watch.sh"),
    # ADAM-BACKUP : se déclenche sur backup:failed (retry) et config:changed
    ("adam-backup", "backup:failed", "bash ~/scripts/backup.sh --retry"),
]

# --- Agents par défaut ---
DEFAULT_AGENTS = [
    ("adam-praetor", "ADAM-PRAETOR — Surveillance système", {"timeout": 120, "retries": 2}),
    ("adam-blue", "ADAM-BLUE — Sécurité 24/24", {"timeout": 180, "retries": 2}),
    ("adam-red", "ADAM-RED — Scan OSINT", {"timeout": 600, "retries": 1}),
    ("adam-sentinel", "ADAM-SENTINEL — Veille technologique", {"timeout": 300, "retries": 1}),
    ("adam-critic", "ADAM-CRITIC — Audit qualité", {"timeout": 300, "retries": 1}),
    ("adam-viz-checker", "ADAM-VIZ-CHECKER — Vérification dashboards", {"timeout": 60, "retries": 3}),
    ("adam-doctor", "ADAM-DOCTOR — Visite médicale", {"timeout": 60, "retries": 3}),
    ("adam-backup", "ADAM-BACKUP — Sauvegarde", {"timeout": 600, "retries": 2}),
    ("adam-cicd", "ADAM-CICD — Intégration continue", {"timeout": 120, "retries": 2}),
    ("adam-monitor", "ADAM-MONITOR — Monitoring hardware", {"timeout": 60, "retries": 3}),
    ("adam-deploy", "ADAM-DEPLOY — Déploiement & restart", {"timeout": 120, "retries": 2}),
    ("adam-evolution", "ADAM-EVOLUTION — Évolution & scan de code", {"timeout": 300, "retries": 1}),
    ("adam-architect", "ADAM-ARCHITECT — Conception & architecture", {"timeout": 300, "retries": 1}),
    ("adam-scribe", "ADAM-SCRIBE — Rédaction & documentation", {"timeout": 120, "retries": 2}),
    ("adam-treasurer", "ADAM-TREASURER — Finance & rentabilité", {"timeout": 60, "retries": 3}),
    ("adam-researcher", "ADAM-RESEARCHER — Veille scientifique biomédicale", {"timeout": 120, "retries": 2}),
    ("adam-social", "ADAM-SOCIAL — Influence virtuelle & monétisation", {"timeout": 120, "retries": 2}),
]


def init_default_subscriptions():
    """Initialise les souscriptions par défaut."""
    bus = EventBus()
    for agent_id, display_name, config in DEFAULT_AGENTS:
        bus.register_agent(agent_id, display_name, config)
    for agent_id, channel, handler in DEFAULT_SUBSCRIPTIONS:
        bus.subscribe(agent_id, channel, handler)
    logger.info(f"{len(DEFAULT_AGENTS)} agents et {len(DEFAULT_SUBSCRIPTIONS)} souscriptions enregistrés")
    return bus


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    if len(sys.argv) < 2:
        print("Usage: event_bus.py [init|stats|publish CHANNEL PAYLOAD|listen]")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "init":
        bus = init_default_subscriptions()
        print(f"✓ Event Bus initialisé: {DB_PATH}")
        print(f"  {len(DEFAULT_AGENTS)} agents enregistrés")
        print(f"  {len(DEFAULT_SUBSCRIPTIONS)} souscriptions créées")
        stats = bus.get_stats()
        print(f"  Stats: {stats}")

    elif cmd == "stats":
        bus = EventBus()
        stats = bus.get_stats()
        print(json.dumps(stats, indent=2, ensure_ascii=False))

    elif cmd == "publish":
        if len(sys.argv) < 4:
            print("Usage: event_bus.py publish CHANNEL 'JSON_PAYLOAD'")
            sys.exit(1)
        channel = sys.argv[2]
        payload = json.loads(sys.argv[3])
        bus = EventBus()
        eid = bus.publish(channel, payload)
        print(f"✓ Événement #{eid} publié sur {channel}")

    else:
        print(f"Commande inconnue: {cmd}")
        sys.exit(1)
