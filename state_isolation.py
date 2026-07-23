#!/usr/bin/env python3
"""
EVA ADAM v2 — Isolation Mémoire/État par Agent (State Isolation)
=================================================================
Levier 3 : Isolation mémoire/état par agent.

Chaque agent ADAM possède sa propre base SQLite dédiée dans
~/.hermes/adams/<agent_id>/state.db, garantissant l'isolation
complète des données d'état entre agents.

Tables par agent :
  - agent_state   : Stockage clé/valeur persistant
  - run_history   : Historique des exécutions (actions, résultats, durée)
  - health_check  : Bilan de santé périodique (status, métriques JSON)
  - counters      : Compteurs atomiques incrémentaux

Usage :
    from state_isolation import AgentState, init_all_states, AGENTS

    # Initialisation complète
    init_all_states()

    # Utilisation par agent
    state = AgentState("adam-sentinel")
    state.set_state("last_scan", "2025-07-22T12:00:00")
    last_scan = state.get_state("last_scan")
    state.record_run("scan", "OK", 1250.5)
    state.record_health("healthy", {"cpu": 45, "ram": 1024})
    state.increment_counter("scans_today")
    history = state.get_history(limit=10)

CLI :
    python3 state_isolation.py --init              # Crée toutes les DBs
    python3 state_isolation.py --status <agent_id>  # État d'un agent
    python3 state_isolation.py --history <agent_id> # Historique d'un agent
"""

import sqlite3
import json
import sys
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

# Répertoire racine des états agents
ADAMS_DIR = Path.home() / ".hermes" / "adams"

# Les 11 agents ADAM v2
AGENTS = [
    "adam-praetor",
    "adam-blue",
    "adam-red",
    "adam-sentinel",
    "adam-critic",
    "adam-viz-checker",
    "adam-doctor",
    "adam-backup",
    "adam-cicd",
    "adam-monitor",
    "adam-deploy",
]

logger = logging.getLogger("eva.adam.state_isolation")


# ---------------------------------------------------------------------------
# Fonctions internes SQL
# ---------------------------------------------------------------------------

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS agent_state (
    key         TEXT PRIMARY KEY,
    value       TEXT NOT NULL,
    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS run_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp   TEXT NOT NULL DEFAULT (datetime('now')),
    action      TEXT NOT NULL,
    result      TEXT NOT NULL,
    duration_ms REAL NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS health_check (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp   TEXT NOT NULL DEFAULT (datetime('now')),
    status      TEXT NOT NULL,
    metrics_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS counters (
    name        TEXT PRIMARY KEY,
    valeur      INTEGER NOT NULL DEFAULT 0,
    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


# ---------------------------------------------------------------------------
# Classe AgentState
# ---------------------------------------------------------------------------

class AgentState:
    """Gestionnaire d'état isolé pour un agent ADAM.

    Chaque instance est liée à un agent unique et opère sur sa propre
    base SQLite dans ~/.hermes/adams/<agent_id>/state.db.

    Args:
        agent_id: Identifiant de l'agent (ex: "adam-sentinel").
        auto_init: Crée le répertoire et la base si inexistants (défaut: True).
    """

    def __init__(self, agent_id: str, auto_init: bool = True) -> None:
        if agent_id not in AGENTS:
            raise ValueError(
                f"Agent inconnu : '{agent_id}'. "
                f"Agents valides : {', '.join(AGENTS)}"
            )
        self.agent_id = agent_id
        self.db_path = ADAMS_DIR / agent_id / "state.db"

        if auto_init:
            self._ensure_db()

    # -----------------------------------------------------------------------
    # Gestion interne de la base
    # -----------------------------------------------------------------------

    def _ensure_db(self) -> None:
        """Crée le répertoire et la base SQLite s'ils n'existent pas."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.db_path.exists():
            logger.info("Création de la base d'état pour %s → %s", self.agent_id, self.db_path)
        conn = self._connect()
        try:
            conn.executescript(_SCHEMA_SQL)
            conn.commit()
        finally:
            conn.close()

    def _connect(self) -> sqlite3.Connection:
        """Retourne une connexion SQLite en mode WAL pour l'agent courant.

        Returns:
            Connexion sqlite3 avec row_factory activé.
        """
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        return conn

    def _now(self) -> str:
        """Retourne le timestamp ISO 8601 UTC courant."""
        return datetime.now(timezone.utc).isoformat()

    # -----------------------------------------------------------------------
    # API publique — État clé/valeur
    # -----------------------------------------------------------------------

    def get_state(self, key: str) -> Optional[str]:
        """Récupère la valeur d'une clé d'état.

        Args:
            key: Nom de la clé à consulter.

        Returns:
            La valeur stockée, ou None si la clé n'existe pas.
        """
        conn = self._connect()
        try:
            cur = conn.execute(
                "SELECT value FROM agent_state WHERE key = ?", (key,)
            )
            row = cur.fetchone()
            return row["value"] if row else None
        finally:
            conn.close()

    def set_state(self, key: str, value: str) -> None:
        """Définit la valeur d'une clé d'état (insertion ou mise à jour).

        Args:
            key: Nom de la clé.
            value: Valeur à stocker (chaîne JSON-sérialisable).
        """
        now = self._now()
        conn = self._connect()
        try:
            conn.execute(
                """INSERT INTO agent_state (key, value, updated_at)
                   VALUES (?, ?, ?)
                   ON CONFLICT(key) DO UPDATE SET
                       value = excluded.value,
                       updated_at = excluded.updated_at""",
                (key, str(value), now),
            )
            conn.commit()
        finally:
            conn.close()

    # -----------------------------------------------------------------------
    # API publique — Historique des exécutions
    # -----------------------------------------------------------------------

    def record_run(
        self, action: str, result: str, duration_ms: float
    ) -> int:
        """Enregistre une exécution dans l'historique de l'agent.

        Args:
            action: Nom de l'action exécutée (ex: "scan", "backup", "alert").
            result: Résultat (ex: "OK", "FAIL", "TIMEOUT").
            duration_ms: Durée de l'exécution en millisecondes.

        Returns:
            L'identifiant (id) de la ligne insérée.
        """
        conn = self._connect()
        try:
            cur = conn.execute(
                """INSERT INTO run_history (timestamp, action, result, duration_ms)
                   VALUES (?, ?, ?, ?)""",
                (self._now(), action, result, duration_ms),
            )
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()

    # -----------------------------------------------------------------------
    # API publique — Bilan de santé
    # -----------------------------------------------------------------------

    def record_health(
        self, status: str, metrics: Optional[Dict[str, Any]] = None
    ) -> int:
        """Enregistre un bilan de santé de l'agent.

        Args:
            status: Statut (ex: "healthy", "degraded", "unhealthy").
            metrics: Dictionnaire de métriques (CPU, RAM, etc.).

        Returns:
            L'identifiant (id) de la ligne insérée.
        """
        metrics_json = json.dumps(metrics or {}, ensure_ascii=False)
        conn = self._connect()
        try:
            cur = conn.execute(
                """INSERT INTO health_check (timestamp, status, metrics_json)
                   VALUES (?, ?, ?)""",
                (self._now(), status, metrics_json),
            )
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()

    # -----------------------------------------------------------------------
    # API publique — Compteurs
    # -----------------------------------------------------------------------

    def increment_counter(self, name: str, delta: int = 1) -> int:
        """Incrémente un compteur et retourne sa nouvelle valeur.

        Crée le compteur avec la valeur initiale s'il n'existe pas.

        Args:
            name: Nom du compteur.
            delta: Valeur d'incrément (défaut: 1).

        Returns:
            Nouvelle valeur du compteur après incrémentation.
        """
        now = self._now()
        conn = self._connect()
        try:
            cur = conn.execute(
                """INSERT INTO counters (name, valeur, updated_at)
                   VALUES (?, ?, ?)
                   ON CONFLICT(name) DO UPDATE SET
                       valeur = valeur + ?,
                       updated_at = ?""",
                (name, delta, now, delta, now),
            )
            conn.commit()
            # Relecture pour obtenir la valeur à jour
            cur = conn.execute(
                "SELECT valeur FROM counters WHERE name = ?", (name,)
            )
            row = cur.fetchone()
            return row["valeur"] if row else delta
        finally:
            conn.close()

    def get_counter(self, name: str) -> int:
        """Retourne la valeur d'un compteur (0 s'il n'existe pas).

        Args:
            name: Nom du compteur.

        Returns:
            Valeur actuelle du compteur, ou 0.
        """
        conn = self._connect()
        try:
            cur = conn.execute(
                "SELECT valeur FROM counters WHERE name = ?", (name,)
            )
            row = cur.fetchone()
            return row["valeur"] if row else 0
        finally:
            conn.close()

    # -----------------------------------------------------------------------
    # API publique — Consultation de l'historique
    # -----------------------------------------------------------------------

    def get_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Retourne les dernières exécutions de l'agent.

        Args:
            limit: Nombre maximal d'entrées à retourner (défaut: 50).

        Returns:
            Liste de dictionnaires représentant chaque ligne de run_history,
            triée par timestamp décroissant.
        """
        conn = self._connect()
        try:
            cur = conn.execute(
                """SELECT id, timestamp, action, result, duration_ms
                   FROM run_history
                   ORDER BY id DESC
                   LIMIT ?""",
                (limit,),
            )
            return [dict(row) for row in cur.fetchall()]
        finally:
            conn.close()

    def get_latest_health(self) -> Optional[Dict[str, Any]]:
        """Retourne le dernier bilan de santé de l'agent.

        Returns:
            Dictionnaire du dernier health_check, ou None.
        """
        conn = self._connect()
        try:
            cur = conn.execute(
                """SELECT id, timestamp, status, metrics_json
                   FROM health_check
                   ORDER BY id DESC
                   LIMIT 1"""
            )
            row = cur.fetchone()
            if row:
                d = dict(row)
                d["metrics"] = json.loads(d.pop("metrics_json"))
                return d
            return None
        finally:
            conn.close()

    def get_all_states(self) -> Dict[str, str]:
        """Retourne toutes les paires clé/valeur de l'agent.

        Returns:
            Dictionnaire complet de l'état clé/valeur.
        """
        conn = self._connect()
        try:
            cur = conn.execute(
                "SELECT key, value FROM agent_state ORDER BY key"
            )
            return {row["key"]: row["value"] for row in cur.fetchall()}
        finally:
            conn.close()


# ---------------------------------------------------------------------------
# Fonctions d'initialisation
# ---------------------------------------------------------------------------

def init_all_states() -> None:
    """Crée les répertoires et bases SQLite pour tous les agents ADAM.

    Parcourt la liste AGENTS et crée pour chacun :
      - ~/.hermes/adams/<agent_id>/
      - ~/.hermes/adams/<agent_id>/state.db (avec toutes les tables)

    Peut être appelé sans risque (idempotent — les tables existantes
    ne sont pas recréées).
    """
    ADAMS_DIR.mkdir(parents=True, exist_ok=True)
    logger.info("Initialisation des états agents dans %s", ADAMS_DIR)

    for agent_id in AGENTS:
        agent_dir = ADAMS_DIR / agent_id
        agent_dir.mkdir(parents=True, exist_ok=True)
        db_path = agent_dir / "state.db"

        # Création de la base et des tables
        conn = sqlite3.connect(str(db_path))
        try:
            conn.executescript(_SCHEMA_SQL)
            conn.commit()
            logger.info("  ✓ %s → %s", agent_id, db_path)
        except sqlite3.Error as exc:
            logger.error("  ✗ %s → ERREUR : %s", agent_id, exc)
        finally:
            conn.close()

    logger.info("Initialisation terminée — %d états agents créés.", len(AGENTS))


def get_agent_status(agent_id: str) -> Dict[str, Any]:
    """Retourne un résumé d'état pour un agent donné.

    Args:
        agent_id: Identifiant de l'agent.

    Returns:
        Dictionnaire contenant le chemin db, le nombre de clés d'état,
        le nombre d'exécutions, le nombre de bilans de santé,
        le dernier bilan de santé, et les compteurs.

    Raises:
        ValueError: Si l'agent est inconnu.
    """
    if agent_id not in AGENTS:
        raise ValueError(f"Agent inconnu : '{agent_id}'")

    state = AgentState(agent_id)
    db_path = state.db_path

    if not db_path.exists():
        return {
            "agent_id": agent_id,
            "db_path": str(db_path),
            "existe": False,
            "message": "La base n'a pas encore été initialisée.",
        }

    conn = state._connect()
    try:
        cur = conn.execute("SELECT COUNT(*) AS cnt FROM agent_state")
        nb_states = cur.fetchone()["cnt"]

        cur = conn.execute("SELECT COUNT(*) AS cnt FROM run_history")
        nb_runs = cur.fetchone()["cnt"]

        cur = conn.execute("SELECT COUNT(*) AS cnt FROM health_check")
        nb_health = cur.fetchone()["cnt"]

        cur = conn.execute("SELECT name, valeur FROM counters ORDER BY name")
        counters = {row["name"]: row["valeur"] for row in cur.fetchall()}

        latest_health = state.get_latest_health()

        return {
            "agent_id": agent_id,
            "db_path": str(db_path),
            "existe": True,
            "nb_cles_etat": nb_states,
            "nb_executions": nb_runs,
            "nb_bilans_sante": nb_health,
            "dernier_bilan_sante": latest_health,
            "compteurs": counters,
        }
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _cli_init() -> None:
    """CLI : initialise toutes les bases d'état des agents."""
    init_all_states()


def _cli_status(agent_id: str) -> None:
    """CLI : affiche le statut détaillé d'un agent.

    Args:
        agent_id: Identifiant de l'agent.
    """
    try:
        status = get_agent_status(agent_id)
    except ValueError as exc:
        print(f"ERREUR : {exc}")
        sys.exit(1)

    print(f"État de l'agent : {status['agent_id']}")
    print(f"  Base          : {status['db_path']}")
    if not status["existe"]:
        print("  ⚠  Base non initialisée — lancer --init d'abord.")
        return

    print(f"  Clés d'état   : {status['nb_cles_etat']}")
    print(f"  Exécutions    : {status['nb_executions']}")
    print(f"  Bilans santé  : {status['nb_bilans_sante']}")

    if status["dernier_bilan_sante"]:
        h = status["dernier_bilan_sante"]
        print(f"  Dernier bilan : {h['status']} ({h['timestamp']})")
        if h["metrics"]:
            print(f"    Métriques   : {json.dumps(h['metrics'], ensure_ascii=False)}")
    else:
        print("  Dernier bilan : (aucun)")

    if status["compteurs"]:
        print("  Compteurs :")
        for name, val in status["compteurs"].items():
            print(f"    {name} = {val}")
    else:
        print("  Compteurs : (aucun)")


def _cli_history(agent_id: str, limit: int = 20) -> None:
    """CLI : affiche l'historique des exécutions d'un agent.

    Args:
        agent_id: Identifiant de l'agent.
        limit: Nombre d'entrées à afficher.
    """
    try:
        state = AgentState(agent_id)
    except ValueError as exc:
        print(f"ERREUR : {exc}")
        sys.exit(1)

    if not state.db_path.exists():
        print(f"⚠  La base de '{agent_id}' n'existe pas. Lancez --init d'abord.")
        return

    history = state.get_history(limit=limit)

    if not history:
        print(f"Aucune exécution enregistrée pour '{agent_id}'.")
        return

    print(f"Historique des exécutions — {agent_id} (dernières {len(history)})")
    print(f"{'ID':>4}  {'Timestamp':<26}  {'Action':<20}  {'Résultat':<10}  {'Durée (ms)':>10}")
    print("-" * 80)
    for entry in history:
        print(
            f"{entry['id']:>4}  "
            f"{entry['timestamp']:<26}  "
            f"{entry['action']:<20}  "
            f"{entry['result']:<10}  "
            f"{entry['duration_ms']:>10.1f}"
        )


def main() -> None:
    """Point d'entrée CLI pour state_isolation.py.

    Usage :
        python3 state_isolation.py --init
        python3 state_isolation.py --status <agent_id>
        python3 state_isolation.py --history <agent_id>
    """
    import argparse

    parser = argparse.ArgumentParser(
        description="ADAM v2 — Isolation mémoire/état par agent",
    )
    parser.add_argument(
        "--init",
        action="store_true",
        help="Initialise les répertoires et bases SQLite pour tous les agents",
    )
    parser.add_argument(
        "--status",
        type=str,
        metavar="AGENT_ID",
        help="Affiche le statut détaillé d'un agent",
    )
    parser.add_argument(
        "--history",
        type=str,
        metavar="AGENT_ID",
        help="Affiche l'historique des exécutions d'un agent",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Nombre d'entrées d'historique à afficher (défaut: 20)",
    )

    args = parser.parse_args()

    # Configuration du logging pour la CLI
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s | %(message)s",
    )

    if args.init:
        _cli_init()
    elif args.status:
        _cli_status(args.status)
    elif args.history:
        _cli_history(args.history, limit=args.limit)
    else:
        parser.print_help()


# ---------------------------------------------------------------------------
# Point d'entrée
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    main()