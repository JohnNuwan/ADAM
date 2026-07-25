#!/usr/bin/env python3
"""
ADAM-EVOLUTION — Agent d'évolution des règles Praetor.

Écoute le canal `adam:healed` publié par self_heal.py après chaque guérison
réussie. Transforme chaque guérison en règle Praetor réutilisable, puis
applique une sélection naturelle (inspirée d'AlphaEvolve de DeepMind) :

  1. CRÉATION — Chaque guérison réussie génère une règle Praetor.
     Si une règle similaire existe déjà, son compteur d'occurrences augmente.
  2. ÉVALUATION — Chaque règle a un score de fitness basé sur son taux de
     succès glissant (20 dernières exécutions). Les règles qui marchent
     voient leur score augmenter, les échecs le diminuent.
  3. SÉLECTION — Les règles dont le score tombe sous un seuil (0.3) sont
     marquées "deprecated" et supprimées après une période de grâce.
  4. MUTATION — Si une règle échoue plusieurs fois, sa correction peut être
     mutée (variante générée à partir des stratégies self_heal connues).

Boucle cible :
  Erreur → adam:error → self_heal → praetor → evolution → auto-résolu
                                        ↑ règle créée ici ↑

Usage :
  python3 adam-evolution.py              # boucle continue (daemon)
  python3 adam-evolution.py --once       # un seul cycle puis exit
  python3 adam-evolution.py --status     # affiche l'état des règles
  python3 adam-evolution.py --dry-run    # simulation sans écriture
"""


import argparse
import json
import logging
import os
import re
import signal
import sqlite3
import sys
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ─── Configuration ──────────────────────────────────────────────────────────

ADAM_V2_DIR = Path(os.environ.get("ADAM_V2_DIR", Path.home() / "eva-adam-v2"))
DB_PATH = ADAM_V2_DIR / "event_bus.db"

# Fichiers Praetor
PRAETOR_DIR = Path.home() / ".praetor"
LEARNED_RULES_FILE = PRAETOR_DIR / "learned_rules.json"
BUILTIN_RULES_FILE = PRAETOR_DIR / "rules.json"

# Fichier de fitness des règles d'évolution
EVOLUTION_DIR = ADAM_V2_DIR / "evolution"
EVOLUTION_DIR.mkdir(parents=True, exist_ok=True)
RULE_FITNESS_FILE = EVOLUTION_DIR / "rule_fitness.json"

# Paramètres d'évolution
HISTORY_LEN = 20          # Historique glissant par règle
DEPRECATION_THRESHOLD = 0.3   # Score < 0.3 → deprecated
GRACE_PERIOD_SEC = 300    # 5 min de grâce avant suppression définitive
POLL_INTERVAL = 10        # Secondes entre chaque cycle
HEARTBEAT_INTERVAL = 60   # Secondes entre chaque heartbeat
CODE_SCAN_INTERVAL = 1800  # 30 min entre chaque scan de code automatique
AGENT_ID = "adam-evolution"
CHANNEL_LISTEN = "adam:healed"

# Mapping canal → pattern d'erreur praetor
CANAL_PATTERN_MAP = {
    "hardware:gpu_alert": r"gpu_alert|vram_high|gpu_\w+",
    "adam:error": r"error|crash|fail|panic|exception",
    "service:down": r"service_down|process_not_found|timeout",
    "disk:full": r"disk_full|no_space|enospc",
    "file:changed": r"file_changed|config_modified",
}

# Mapping stratégies self_heal → corrections praetor connues
STRATEGIE_CORRECTION_MAP = {
    "restart_service": "systemctl restart SERVICE || pkill -f PROCESS && sleep 2 && python3 SCRIPT &",
    "clean_disk": "find /tmp /var/log -type f -mtime +7 -delete; journalctl --vacuum-size=100M",
    "free_vram": "nvidia-smi --query-compute-apps=pid --format=csv,noheader | xargs -r kill -9",
    "retry": "sleep 5 && RETRY_COMMAND",
    "restart_docker": "docker restart CONTAINER",
    "kill_zombie": "kill -9 PID",
    "clear_cache": "sync && echo 3 > /proc/sys/vm/drop_caches",
}

# ─── Logging ────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [evolution] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("adam-evolution")

# ─── Détecteur d'arrêt propre ───────────────────────────────────────────────

_running = True


def _signal_handler(signum: int, frame: Any) -> None:
    global _running
    _running = False
    logger.info(f"Signal {signum} reçu — arrêt en cours...")


signal.signal(signal.SIGTERM, _signal_handler)
signal.signal(signal.SIGINT, _signal_handler)


# ─── Gestion du fichier de fitness des règles ───────────────────────────────


def _load_rule_fitness() -> dict[str, Any]:
    """Charge les scores de fitness des règles d'évolution."""
    default: dict[str, Any] = {}
    if RULE_FITNESS_FILE.exists():
        try:
            data = json.loads(RULE_FITNESS_FILE.read_text(encoding="utf-8"))
            return data
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Impossible de charger rule_fitness.json: {e}")
    return default


def _save_rule_fitness(data: dict[str, Any]) -> None:
    """Sauvegarde les scores de fitness des règles."""
    try:
        RULE_FITNESS_FILE.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except OSError as e:
        logger.warning(f"Impossible de sauvegarder rule_fitness.json: {e}")


def _init_rule_fitness(rule_id: str) -> dict[str, Any]:
    """Initialise le fitness pour une nouvelle règle."""
    return {
        "score": 1.0,
        "history": [],
        "total": 0,
        "successes": 0,
        "failures": 0,
        "deprecated": False,
        "deprecated_at": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "last_used": None,
        "occurrences": 0,
    }


def _update_rule_fitness(
    rule_id: str, succes: bool, fitness_data: dict[str, Any]
) -> dict[str, Any]:
    """Met à jour le score de fitness d'une règle après utilisation.

    Calcul inspiré d'AlphaEvolve :
    - Score = moyenne de l'historique glissant (20 dernières exécutions)
    - Succès = 1.0, Échec = 0.0
    - Si score < DEPRECATION_THRESHOLD → deprecated
    """
    if rule_id not in fitness_data:
        fitness_data[rule_id] = _init_rule_fitness(rule_id)

    entry = fitness_data[rule_id]
    entry["history"].append(1 if succes else 0)
    if len(entry["history"]) > HISTORY_LEN:
        entry["history"].pop(0)

    entry["total"] += 1
    if succes:
        entry["successes"] += 1
    else:
        entry["failures"] += 1

    entry["last_used"] = datetime.now(timezone.utc).isoformat()
    entry["score"] = sum(entry["history"]) / len(entry["history"])

    # Vérifier la dépréciation
    if entry["score"] < DEPRECATION_THRESHOLD and not entry["deprecated"]:
        entry["deprecated"] = True
        entry["deprecated_at"] = datetime.now(timezone.utc).isoformat()
        logger.warning(
            f"Règle {rule_id} dépréciée (score={entry['score']:.2f})"
        )

    # Si la règle était dépréciée mais s'améliore, la réactiver
    if entry["deprecated"] and entry["score"] >= DEPRECATION_THRESHOLD:
        entry["deprecated"] = False
        entry["deprecated_at"] = None
        logger.info(
            f"Règle {rule_id} réactivée (score remonté à {entry['score']:.2f})"
        )

    return entry


# ─── Gestion des règles Praetor ─────────────────────────────────────────────


def _load_learned_rules() -> dict[str, Any]:
    """Charge les règles apprises de Praetor."""
    if LEARNED_RULES_FILE.exists():
        try:
            return json.loads(LEARNED_RULES_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {"version": "2.0", "rules": []}


def _save_learned_rules(data: dict[str, Any]) -> None:
    """Sauvegarde les règles apprises de Praetor."""
    PRAETOR_DIR.mkdir(parents=True, exist_ok=True)
    LEARNED_RULES_FILE.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _load_builtin_rules() -> list[dict[str, Any]]:
    """Charge les règles builtin pour éviter les doublons."""
    if BUILTIN_RULES_FILE.exists():
        try:
            data = json.loads(BUILTIN_RULES_FILE.read_text(encoding="utf-8"))
            return data.get("rules", [])
        except (json.JSONDecodeError, OSError):
            pass
    return []


def _find_existing_rule(
    rules: list[dict[str, Any]], pattern: str
) -> dict[str, Any] | None:
    """Cherche une règle existante par pattern (match exact ou regex)."""
    for rule in rules:
        if rule.get("pattern") == pattern:
            return rule
        # Match aussi si le pattern existant contient le nouveau
        try:
            if re.search(rule.get("pattern", ""), pattern):
                return rule
        except re.error:
            continue
    return None


def _generer_pattern(canal: str, resolution: dict[str, Any]) -> str:
    """Génère un pattern d'erreur praetor à partir du canal et de la résolution.

    Le pattern doit matcher les futures erreurs similaires pour que praetor
    puisse appliquer la correction automatiquement.
    """
    # Pattern de base selon le canal
    base_pattern = CANAL_PATTERN_MAP.get(canal, r"error|crash|fail")

    # Affiner selon l'action de résolution
    action = resolution.get("action", "")
    if action == "free_vram":
        return r"vram_high|gpu_alert|out_of_memory|cuda.*error"
    elif action == "restart_service":
        return r"service_down|process_not_found|connection_refused|timeout"
    elif action == "clean_disk":
        return r"disk_full|no_space|enospc|disk_space"
    elif action == "retry":
        return r"timeout|connection_reset|temporary_failure|retry"
    elif action == "restart_docker":
        return r"docker.*unhealthy|container.*restart|docker.*error"
    elif action == "kill_zombie":
        return r"zombie|defunct|process.*stale"
    elif action == "clear_cache":
        return r"cache.*full|memory.*pressure|oom"

    return base_pattern


def _generer_correction(resolution: dict[str, Any]) -> str:
    """Génère une commande de correction praetor à partir de la résolution."""
    action = resolution.get("action", "retry")
    return STRATEGIE_CORRECTION_MAP.get(action, "ANALYZE")


def _generer_description(
    canal: str, resolution: dict[str, Any], fitness: dict[str, Any]
) -> str:
    """Génère une description lisible pour la règle."""
    action = resolution.get("action", "inconnu")
    detail = resolution.get("detail", "")
    score = fitness.get("score", 1.0)
    total = fitness.get("total", 0)

    desc = f"Auto-générée par adam-evolution (canal={canal}, stratégie={action})"
    if detail:
        desc += f" — {detail}"
    desc += f" [fitness={score:.2f}, n={total}]"
    return desc


def creer_regle_praetor(
    event_id: int,
    canal: str,
    resolution: dict[str, Any],
    fitness: dict[str, Any],
    dry_run: bool = False,
) -> str | None:
    """Crée ou met à jour une règle Praetor à partir d'un event adam:healed.

    Returns:
        L'ID de la règle créée/mise à jour, ou None si ignoré.
    """
    # Ignorer les guérisons sans succès
    if not resolution.get("succes", False):
        logger.debug(
            f"Event #{event_id} ignoré (guérison sans succès)"
        )
        return None

    pattern = _generer_pattern(canal, resolution)
    correction = _generer_correction(resolution)
    description = _generer_description(canal, resolution, fitness)
    action = resolution.get("action", "inconnu")
    rule_id_base = f"evo-{action}-{canal.replace(':', '_')}"

    # Charger les règles existantes
    data = _load_learned_rules()
    rules = data.get("rules", [])

    # Vérifier les règles builtin pour éviter les doublons
    builtin_rules = _load_builtin_rules()
    for br in builtin_rules:
        try:
            if re.search(br.get("pattern", ""), pattern):
                logger.info(
                    f"Règle builtin '{br.get('id')}' couvre déjà ce pattern "
                    f"— skip"
                )
                return None
        except re.error:
            continue

    # Chercher une règle existante
    existing = _find_existing_rule(rules, pattern)
    if existing:
        # Mettre à jour les occurrences et le last_seen
        existing["occurrences"] = existing.get("occurrences", 0) + 1
        existing["last_seen"] = datetime.now(timezone.utc).isoformat().split("T")[0]
        existing["description"] = description  # Mettre à jour avec le fitness
        rule_id = existing["id"]
        logger.info(
            f"Règle existante {rule_id} mise à jour "
            f"(occurrences={existing['occurrences']})"
        )
    else:
        # Créer une nouvelle règle
        rule_id = rule_id_base
        # S'assurer de l'unicité de l'ID
        existing_ids = {r.get("id") for r in rules}
        if rule_id in existing_ids:
            rule_id = f"{rule_id_base}-{len(rules) + 1:03d}"

        new_rule = {
            "id": rule_id,
            "pattern": pattern,
            "description": description,
            "severity": "warning",
            "correction": correction,
            "source": "adam-evolution",
            "first_seen": datetime.now(timezone.utc).isoformat().split("T")[0],
            "last_seen": datetime.now(timezone.utc).isoformat().split("T")[0],
            "occurrences": 1,
            "strategie": action,
            "fitness_score": fitness.get("score", 1.0),
            "event_origin": event_id,
        }
        rules.append(new_rule)
        data["rules"] = rules
        data["version"] = "2.0"
        data["last_evolution"] = datetime.now(timezone.utc).isoformat()

        logger.info(
            f"NOUVELLE RÈGLE créée : {rule_id} "
            f"(pattern='{pattern}', correction='{correction[:50]}...')"
        )

    if not dry_run:
        _save_learned_rules(data)

    return rule_id


# ─── Sélection naturelle ────────────────────────────────────────────────────


def selection_naturelle(
    dry_run: bool = False
) -> dict[str, list[str]]:
    """Évalue toutes les règles et supprime les obsolètes.

    Parcourt les règles apprises, vérifie leur fitness, et supprime
    celles qui sont dépréciées depuis plus de GRACE_PERIOD_SEC.

    Returns:
        Dict avec 'supprimees' et 'depreciees' (listes d'IDs).
    """
    fitness_data = _load_rule_fitness()
    rules_data = _load_learned_rules()
    rules = rules_data.get("rules", [])

    now = datetime.now(timezone.utc)
    supprimees: list[str] = []
    depreciees: list[str] = []
    gardez: list[dict[str, Any]] = []

    for rule in rules:
        rule_id = rule.get("id", "")
        fitness = fitness_data.get(rule_id)

        if not fitness:
            # Pas de fitness tracking → garder la règle
            gardez.append(rule)
            continue

        if fitness.get("deprecated", False):
            deprecated_at = fitness.get("deprecated_at")
            if deprecated_at:
                try:
                    dep_time = datetime.fromisoformat(deprecated_at)
                    age = (now - dep_time).total_seconds()
                    if age > GRACE_PERIOD_SEC:
                        supprimees.append(rule_id)
                        logger.info(
                            f"SÉLECTION: Règle {rule_id} supprimée "
                            f"(dépréciée depuis {int(age)}s, "
                            f"score={fitness.get('score', 0):.2f})"
                        )
                        continue
                    else:
                        depreciees.append(rule_id)
                        gardez.append(rule)
                        continue
                except (ValueError, TypeError):
                    pass
        else:
            # Mettre à jour le fitness_score dans la règle
            rule["fitness_score"] = fitness.get("score", 1.0)
            gardez.append(rule)

    # Sauvegarder si des changements
    if supprimees:
        rules_data["rules"] = gardez
        rules_data["last_selection"] = datetime.now(timezone.utc).isoformat()
        if not dry_run:
            _save_learned_rules(rules_data)
        logger.info(
            f"SÉLECTION NATURELLE: {len(supprimees)} supprimée(s), "
            f"{len(depreciees)} dépréciée(s), {len(gardez)} conservée(s)"
        )

    return {"supprimees": supprimees, "depreciees": depreciees}


# ─── Wrapper de bus d'events (similaire à HealBus de self_heal) ──────────────


class EvolutionBus:
    """Wrapper d'accès au bus d'events pour adam-evolution."""

    def __init__(self, db_path: Path = DB_PATH) -> None:
        self.db_path = db_path
        self._conn: sqlite3.Connection | None = None

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def get_healed_events(
        self, last_id: int = 0
    ) -> list[sqlite3.Row]:
        """Récupère les events adam:healed non traités par l'évolution.

        Cherche les events sur le canal adam:healed avec status 'pending'
        ou 'done' (car ils sont publiés par self_heal et déjà marqués done).
        On utilise un curseur last_id pour ne traiter chaque event qu'une fois.
        """
        conn = self._get_conn()
        rows = conn.execute(
            """SELECT id, source, payload, created_at, status
               FROM events
               WHERE channel = ? AND id > ?
               ORDER BY id ASC""",
            (CHANNEL_LISTEN, last_id),
        ).fetchall()
        return rows

    def marquer_traite(self, event_id: int, succes: bool = True) -> None:
        """Marque un event comme traité par l'évolution."""
        conn = self._get_conn()
        now = datetime.now(timezone.utc).isoformat()
        status = "done" if succes else "failed"
        conn.execute(
            """UPDATE events SET processed_at = ?, status = ?
               WHERE id = ?""",
            (now, status, event_id),
        )
        conn.commit()

    def publier(
        self, channel: str, payload: dict, source: str = AGENT_ID
    ) -> int:
        """Publie un event sur le bus."""
        conn = sqlite3.connect(str(self.db_path))
        now = datetime.now(timezone.utc).isoformat()
        cursor = conn.execute(
            """INSERT INTO events (channel, source, payload, priority, created_at, status)
               VALUES (?, ?, ?, 0, ?, 'pending')""",
            (channel, source, json.dumps(payload, ensure_ascii=False), now),
        )
        conn.commit()
        event_id = cursor.lastrowid
        conn.close()
        return event_id

    def heartbeat(self) -> None:
        """Publie un heartbeat sur le bus."""
        self.publier("adam:heartbeat", {
            "agent_id": AGENT_ID,
            "pid": os.getpid(),
            "status": "running",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })


# ─── Analyseur de code source ────────────────────────────────────────────────
#
# Module d'analyse statique du code : complexité cyclomatique, duplication,
# dead code (imports/fonctions inutilisés), et suggestions de factorisation.
# Utilise uniquement le module `ast` de la stdlib — zéro dépendance externe.


import ast
import hashlib
from collections import defaultdict


# Dossiers à ignorer lors du scan (noms exacts + patterns)
_CODE_SCAN_EXCLUDE = {
    "__pycache__", ".git", "node_modules", ".venv", "venv",
    "env", ".tox", ".eggs", "build", "dist", "site-packages",
    "osint_env", ".env", "tests", "test", "_tests",
}

# Patterns de noms de dossiers à exclure (suffixes)
_CODE_SCAN_EXCLUDE_SUFFIXES = ("_env", "-env", ".egg-info")


def _is_excluded_dir(path: Path) -> bool:
    """Vérifie si un chemin contient un dossier à exclure."""
    for part in path.parts:
        if part in _CODE_SCAN_EXCLUDE:
            return True
        for suffix in _CODE_SCAN_EXCLUDE_SUFFIXES:
            if part.endswith(suffix) and len(part) > len(suffix):
                return True
    return False

# Seuils de complexité cyclomatique
_COMPLEXITY_WARN = 10    # > 10 = warning
_COMPLEXITY_CRIT = 20    # > 20 = critical

# Taille minimale (lignes) pour détecter la duplication
_DUP_MIN_LINES = 6
_DUP_MIN_TOKENS = 30


class CodeAnalyzer:
    """Analyse statique du code Python pour optimisation et factorisation."""

    def __init__(self, root_path: Path) -> None:
        self.root = root_path
        self.findings: list[dict[str, Any]] = []
        self._files_scanned = 0
        self._total_lines = 0

    # ─── API publique ────────────────────────────────────────────────────────

    def scan(self) -> dict[str, Any]:
        """Scanne tous les fichiers .py sous root_path et retourne un rapport.

        Returns:
            Dict avec 'findings' (liste), 'summary' (stats), 'files_scanned'.
        """
        self.findings = []
        self._files_scanned = 0
        self._total_lines = 0

        all_funcs: list[dict[str, Any]] = []
        all_blocks: dict[str, list[tuple[str, int, int]]] = defaultdict(list)

        for py_file in self._iter_python_files():
            try:
                source = py_file.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue

            self._files_scanned += 1
            self._total_lines += source.count("\n") + 1

            try:
                tree = ast.parse(source, filename=str(py_file))
            except SyntaxError as e:
                self._add_finding(
                    "syntax_error", "critical", str(py_file), e.lineno or 0,
                    f"Erreur de syntaxe: {e.msg}",
                )
                continue

            rel = str(py_file.relative_to(self.root))

            # 1. Complexité cyclomatique
            for func_info in self._analyze_complexity(tree, rel):
                all_funcs.append(func_info)
                self._check_complexity(func_info)

            # 2. Imports inutilisés
            self._check_unused_imports(tree, rel, source)

            # 3. Dead code (fonctions jamais appelées dans ce fichier)
            self._check_dead_functions(tree, rel)

            # 4. Duplication de code (hash de blocs)
            for block_hash, start, end in self._extract_blocks(source, rel):
                all_blocks[block_hash].append((rel, start, end))

        # 5. Duplication cross-fichiers
        self._check_duplication(all_blocks)

        # 6. Factorisation (fonctions similaires)
        self._check_factorization(all_funcs)

        return self._build_report()

    # ─── Parcours des fichiers ──────────────────────────────────────────────

    def _iter_python_files(self) -> list[Path]:
        """Retourne tous les fichiers .py sous root, hors dossiers exclus."""
        files: list[Path] = []
        for path in self.root.rglob("*.py"):
            if _is_excluded_dir(path):
                continue
            # Skip les fichiers trop gros (> 500 KB = probablement generated)
            try:
                if path.stat().st_size > 512_000:
                    continue
            except OSError:
                continue
            files.append(path)
        return files

    # ─── 1. Complexité cyclomatique ──────────────────────────────────────────

    def _analyze_complexity(
        self, tree: ast.AST, filename: str
    ) -> list[dict[str, Any]]:
        """Calcule la complexité cyclomatique de chaque fonction."""
        results: list[dict[str, Any]] = []

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue

            complexity = 1  # Base
            for child in ast.walk(node):
                if isinstance(child, (ast.If, ast.While, ast.For, ast.AsyncFor)):
                    complexity += 1
                elif isinstance(child, ast.ExceptHandler):
                    complexity += 1
                elif isinstance(child, ast.BoolOp):
                    complexity += len(child.values) - 1
                elif isinstance(child, (ast.ListComp, ast.SetComp,
                                        ast.DictComp, ast.GeneratorExp)):
                    complexity += 1
                elif isinstance(child, ast.Assert):
                    complexity += 1

            results.append({
                "name": node.name,
                "file": filename,
                "line": node.lineno,
                "complexity": complexity,
                "args": len(node.args.args),
            })

        return results

    def _check_complexity(self, func: dict[str, Any]) -> None:
        """Ajoute un finding si la complexité est trop élevée."""
        cx = func["complexity"]
        if cx > _COMPLEXITY_CRIT:
            self._add_finding(
                "high_complexity", "critical", func["file"], func["line"],
                f"Fonction '{func['name']}' complexité={cx} "
                f"(> {_COMPLEXITY_CRIT}) — refactoriser en sous-fonctions",
                suggestion="Diviser en fonctions plus petites, extraire la logique",
            )
        elif cx > _COMPLEXITY_WARN:
            self._add_finding(
                "high_complexity", "warning", func["file"], func["line"],
                f"Fonction '{func['name']}' complexité={cx} "
                f"(> {_COMPLEXITY_WARN}) — considérer refactoriser",
            )

    # ─── 2. Imports inutilisés ───────────────────────────────────────────────

    def _check_unused_imports(
        self, tree: ast.AST, filename: str, source: str
    ) -> None:
        """Détecte les imports qui ne sont pas utilisés dans le fichier."""
        imported: list[tuple[str, str, int]] = []  # (name, alias, line)

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.asname or alias.name.split(".")[0]
                    imported.append((name, alias.asname or alias.name, node.lineno))
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    if alias.name == "*":
                        continue
                    name = alias.asname or alias.name
                    imported.append((name, alias.asname or alias.name, node.lineno))

        # Vérifier si le nom apparaît ailleurs dans le source (hors ligne d'import)
        for name, orig, line in imported:
            # Compter les occurrences hors les lignes d'import
            lines = source.split("\n")
            usage_count = 0
            for i, src_line in enumerate(lines, 1):
                if i == line:
                    continue
                # Match word boundary
                if re.search(rf"\b{re.escape(name)}\b", src_line):
                    usage_count += 1
            if usage_count == 0:
                self._add_finding(
                    "unused_import", "info", filename, line,
                    f"Import '{orig}' non utilisé — supprimer",
                    suggestion=f"Retirer: import {orig}",
                )

    # ─── 3. Dead code (fonctions jamais appelées) ────────────────────────────

    def _check_dead_functions(self, tree: ast.AST, filename: str) -> None:
        """Détecte les fonctions privées (_xxx) jamais appelées dans le fichier."""
        # Collecter toutes les fonctions définies
        defined_funcs: list[tuple[str, int]] = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name.startswith("_") and node.name != "__init__":
                    defined_funcs.append((node.name, node.lineno))

        if not defined_funcs:
            return

        # Collecter tous les noms référencés (appels, attributs)
        referenced: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                referenced.add(node.attr)
            elif isinstance(node, ast.Name):
                referenced.add(node.id)

        for name, line in defined_funcs:
            if name not in referenced:
                self._add_finding(
                    "dead_code", "warning", filename, line,
                    f"Fonction privée '{name}' jamais appelée — dead code",
                    suggestion=f"Supprimer la fonction '{name}'",
                )

    # ─── 4. Duplication de code ──────────────────────────────────────────────

    def _extract_blocks(
        self, source: str, filename: str
    ) -> list[tuple[str, int, int]]:
        """Extrait les blocs de code (fonctions) et les hash pour détection de doublons."""
        try:
            tree = ast.parse(source, filename=filename)
        except SyntaxError:
            return []

        blocks: list[tuple[str, int, int]] = []
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            # Normaliser: extraire le body, retirer docstrings et noms
            try:
                body_str = ast.dump(node, annotate_fields=False)
            except Exception:
                continue
            # Hash de la structure (sans les noms de variables)
            block_hash = hashlib.md5(body_str.encode()).hexdigest()
            blocks.append((block_hash, node.lineno, node.end_lineno or node.lineno))

        return blocks

    def _check_duplication(
        self, all_blocks: dict[str, list[tuple[str, int, int]]]
    ) -> None:
        """Signale les blocs dupliqués (même hash, fichiers différents)."""
        for block_hash, locations in all_blocks.items():
            if len(locations) < 2:
                continue
            # Au moins 2 fichiers différents
            files = {loc[0] for loc in locations}
            if len(files) < 2:
                continue  # Même fichier = surcharge, pas dup
            files_str = ", ".join(f"{l[0]}:{l[1]}" for l in locations[:4])
            self._add_finding(
                "duplication", "warning", locations[0][0], locations[0][1],
                f"Bloc de code dupliqué dans {len(locations)} fichier(s): {files_str}",
                suggestion="Extraire en fonction partagée",
            )

    # ─── 5. Factorisation (fonctions similaires) ─────────────────────────────

    def _check_factorization(self, all_funcs: list[dict[str, Any]]) -> None:
        """Détecte les fonctions avec signatures similaires (potentielle factorisation)."""
        # Grouper par nombre d'args + complexité similaire
        by_profile: dict[tuple, list[dict[str, Any]]] = defaultdict(list)
        for func in all_funcs:
            # Profile: (nb_args, complexity_bucket)
            cx_bucket = func["complexity"] // 5  # Buckets de 5
            profile = (func["args"], cx_bucket)
            by_profile[profile].append(func)

        for profile, funcs in by_profile.items():
            if len(funcs) < 3:
                continue
            # Noms similaires ? (préfixe commun)
            names = [f["name"] for f in funcs]
            # Détecter préfixes communs de 3+ chars
            prefixes: dict[str, int] = defaultdict(int)
            for name in names:
                for length in range(3, min(len(name), 10) + 1):
                    prefixes[name[:length]] += 1

            best_prefix = ""
            best_count = 0
            for prefix, count in prefixes.items():
                if count >= 3 and count > best_count:
                    best_prefix = prefix
                    best_count = count

            if best_prefix and best_count >= 3:
                similar = [f for f in funcs if f["name"].startswith(best_prefix)]
                files_str = ", ".join(
                    f"{f['name']}({f['file']}:{f['line']})" for f in similar[:4]
                )
                self._add_finding(
                    "factorization", "info", similar[0]["file"], similar[0]["line"],
                    f"{len(similar)} fonctions similaires (préfixe '{best_prefix}'): "
                    f"{files_str}",
                    suggestion=f"Considérer une factory ou classe de base pour '{best_prefix}...'",
                )

    # ─── Helpers ─────────────────────────────────────────────────────────────

    def _add_finding(
        self,
        finding_type: str,
        severity: str,
        file: str,
        line: int,
        message: str,
        suggestion: str = "",
    ) -> None:
        self.findings.append({
            "type": finding_type,
            "severity": severity,
            "file": file,
            "line": line,
            "message": message,
            "suggestion": suggestion,
        })

    def _build_report(self) -> dict[str, Any]:
        by_severity = defaultdict(int)
        by_type = defaultdict(int)
        for f in self.findings:
            by_severity[f["severity"]] += 1
            by_type[f["type"]] += 1

        return {
            "findings": self.findings,
            "summary": {
                "total": len(self.findings),
                "critical": by_severity["critical"],
                "warning": by_severity["warning"],
                "info": by_severity["info"],
                "by_type": dict(by_type),
            },
            "files_scanned": self._files_scanned,
            "total_lines": self._total_lines,
        }


# ─── Agent principal ────────────────────────────────────────────────────────


class AdamEvolution:
    """Agent adam-evolution : écoute adam:healed, crée et fait évoluer les règles."""

    def __init__(
        self,
        dry_run: bool = False,
        once: bool = False,
    ) -> None:
        self.dry_run = dry_run
        self.once = once
        self.bus = EvolutionBus()
        self._last_id = self._load_cursor()  # Curseur persistant
        self._cycles = 0
        self._dernier_heartbeat = 0.0
        self._regle_stats = {"creees": 0, "mises_a_jour": 0, "supprimees": 0}
        self._dernier_scan_code = 0.0  # Timestamp du dernier scan de code
        self._code_scan_findings: list[dict[str, Any]] = []  # Cache findings

    def _load_cursor(self) -> int:
        """Charge le curseur du dernier event traité."""
        cursor_file = EVOLUTION_DIR / "evolution_cursor.txt"
        if cursor_file.exists():
            try:
                return int(cursor_file.read_text().strip())
            except (ValueError, OSError):
                pass
        return 0

    def _save_cursor(self) -> None:
        """Sauvegarde le curseur du dernier event traité."""
        cursor_file = EVOLUTION_DIR / "evolution_cursor.txt"
        try:
            cursor_file.write_text(str(self._last_id))
        except OSError as e:
            logger.warning(f"Impossible de sauvegarder le curseur: {e}")

    def _process_healed_event(self, row: sqlite3.Row) -> None:
        """Traite un event adam:healed individuel."""
        event_id = row["id"]
        raw_payload = row["payload"]  # Le JSON est dans 'payload' (colonne payload)

        try:
            payload = json.loads(raw_payload) if raw_payload else {}
        except json.JSONDecodeError:
            logger.warning(f"Event #{event_id} : payload JSON invalide — skip")
            self.bus.marquer_traite(event_id, succes=False)
            return

        # Vérifier que c'est bien une guérison réussie
        healed = payload.get("healed", False)
        resolution = payload.get("resolution", {})
        canal_origine = payload.get("channel", "unknown")
        strategie = payload.get("strategie", "inconnu")
        fitness_payload = payload.get("fitness", {})

        if not healed:
            logger.debug(
                f"Event #{event_id} : healed=False — skip"
            )
            self.bus.marquer_traite(event_id, succes=True)
            return

        logger.info(
            f"Traitement event #{event_id} : canal_origine={canal_origine}, "
            f"stratégie={strategie}, fitness_score={fitness_payload.get('score', '?')}"
        )

        # Créer ou mettre à jour la règle praetor
        rule_id = creer_regle_praetor(
            event_id=event_id,
            canal=canal_origine,
            resolution=resolution,
            fitness=fitness_payload,
            dry_run=self.dry_run,
        )

        if rule_id:
            # Mettre à jour le fitness de la règle
            fitness_data = _load_rule_fitness()
            _update_rule_fitness(rule_id, succes=True, fitness_data=fitness_data)
            if not self.dry_run:
                _save_rule_fitness(fitness_data)

            self._regle_stats["creees"] += 1
            logger.info(
                f"Règle {rule_id} créée/mise à jour "
                f"(fitness={fitness_data[rule_id]['score']:.2f})"
            )

            # Publier un event praetor:rule_created pour notification
            if not self.dry_run:
                self.bus.publier("praetor:rule_created", {
                    "rule_id": rule_id,
                    "pattern": _generer_pattern(canal_origine, resolution),
                    "strategie": strategie,
                    "fitness_score": fitness_data[rule_id]["score"],
                    "source_event": event_id,
                })

            # Notifier l'architecte pour qu'il review le code des handlers
            # qui ont généré l'erreur → evolution:code_review
            if not self.dry_run:
                self.bus.publier("evolution:code_review", {
                    "type": "rule_learned",
                    "rule_id": rule_id,
                    "pattern": _generer_pattern(canal_origine, resolution),
                    "strategie": strategie,
                    "fitness_score": fitness_data[rule_id]["score"],
                    "source_event": event_id,
                    "canal_origine": canal_origine,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
                logger.info(
                    f"Règle {rule_id} notifiée à l'architecte via evolution:code_review"
                )
        else:
            logger.debug(
                f"Event #{event_id} : aucune règle créée (doublon ou skip)"
            )

        self.bus.marquer_traite(event_id, succes=True)

    def scan_code(self, root_dir: str = "") -> dict[str, Any]:
        """Scanne le code source pour optimisation, factorisation, dead code.

        Args:
            root_dir: Répertoire à scanner (défaut: eva-adam-v2/).

        Returns:
            Rapport d'analyse (findings, summary, files_scanned).
        """
        scan_root = Path(root_dir) if root_dir else ADAM_V2_DIR
        if not scan_root.exists():
            logger.warning(f"Répertoire de scan introuvable: {scan_root}")
            return {"error": "dir not found", "findings": [], "summary": {}}

        logger.info(f"Scan de code source: {scan_root}")
        analyzer = CodeAnalyzer(scan_root)
        report = analyzer.scan()

        s = report.get("summary", {})
        logger.info(
            f"Scan terminé: {report.get('files_scanned', 0)} fichiers, "
            f"{report.get('total_lines', 0)} lignes — "
            f"{s.get('total', 0)} findings "
            f"(🔴{s.get('critical', 0)} 🟡{s.get('warning', 0)} 🔵{s.get('info', 0)})"
        )

        # Publier les findings critiques sur le bus
        if not self.dry_run:
            critical_findings = [
                f for f in report.get("findings", [])
                if f.get("severity") == "critical"
            ]
            if critical_findings:
                self.bus.publier("evolution:code_review", {
                    "scan_root": str(scan_root),
                    "files_scanned": report.get("files_scanned", 0),
                    "total_lines": report.get("total_lines", 0),
                    "summary": s,
                    "critical_findings": critical_findings[:20],
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
                logger.info(
                    f"{len(critical_findings)} finding(s) critique(s) "
                    f"publié(s) sur evolution:code_review"
                )

        # Sauvegarder le rapport complet sur disque
        if not self.dry_run:
            report_file = EVOLUTION_DIR / "code_review_report.json"
            try:
                report_file.write_text(
                    json.dumps(report, indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )
            except OSError as e:
                logger.warning(f"Impossible de sauvegarder le rapport: {e}")

        self._code_scan_findings = report.get("findings", [])
        self._dernier_scan_code = time.time()

        return report

    def _run_periodic_code_scan(self) -> None:
        """Lance un scan de code périodique (toutes les 30 min)."""
        maintenant = time.time()
        if maintenant - self._dernier_scan_code < CODE_SCAN_INTERVAL:
            return

        # Ne scanner que si des fichiers .py existent
        py_files = list(ADAM_V2_DIR.rglob("*.py"))
        if not py_files:
            return

        logger.info("Scan de code périodique déclenché")
        try:
            self.scan_code()
        except Exception as e:
            logger.error(f"Erreur scan de code: {e}", exc_info=True)

    def run_cycle(self) -> None:
        """Exécute un cycle de traitement."""
        self._cycles += 1

        # 1. Récupérer les nouveaux events adam:healed
        rows = self.bus.get_healed_events(last_id=self._last_id)
        if rows:
            logger.info(
                f"Cycle {self._cycles} : {len(rows)} event(s) adam:healed à traiter"
            )
        for row in rows:
            self._last_id = max(self._last_id, row["id"])
            self._process_healed_event(row)

        # Sauvegarder le curseur si on a traité des events
        if rows and not self.dry_run:
            self._save_cursor()

        # 2. Sélection naturelle (toutes les 5 cycles)
        if self._cycles % 5 == 0:
            result = selection_naturelle(dry_run=self.dry_run)
            if result["supprimees"]:
                self._regle_stats["supprimees"] += len(result["supprimees"])
            if result["supprimees"] or result["depreciees"]:
                logger.info(
                    f"Sélection: {len(result['supprimees'])} supprimée(s), "
                    f"{len(result['depreciees'])} dépréciée(s)"
                )

        # 3. Scan de code périodique (toutes les 30 min)
        self._run_periodic_code_scan()

        # 4. Heartbeat
        maintenant = time.time()
        if maintenant - self._dernier_heartbeat >= HEARTBEAT_INTERVAL:
            self.bus.heartbeat()
            self._dernier_heartbeat = maintenant

    def run(self) -> int:
        """Boucle principale de l'agent."""
        logger.info(
            f"Démarrage adam-evolution "
            f"(dry_run={self.dry_run}, once={self.once}) — "
            f"DB={DB_PATH}"
        )

        # Heartbeat initial
        self.bus.heartbeat()
        self._dernier_heartbeat = time.time()

        while _running:
            try:
                self.run_cycle()
            except Exception as e:
                logger.error(f"Erreur cycle {self._cycles}: {e}", exc_info=True)

            if self.once:
                break

            time.sleep(POLL_INTERVAL)

        # Résumé final
        logger.info(
            f"Arrêt adam-evolution — "
            f"{self._cycles} cycles, "
            f"{self._regle_stats['creees']} règle(s) créées, "
            f"{self._regle_stats['supprimees']} supprimée(s)"
        )
        return 0

    def status(self) -> int:
        """Affiche l'état des règles d'évolution."""
        rules_data = _load_learned_rules()
        rules = rules_data.get("rules", [])
        fitness_data = _load_rule_fitness()

        # Filtrer les règles créées par adam-evolution
        evo_rules = [r for r in rules if r.get("source") == "adam-evolution"]

        print(f"\n{'='*70}")
        print(f"ADAM-EVOLUTION — État des règles")
        print(f"{'='*70}")
        print(f"Total règles apprises : {len(rules)}")
        print(f"Règles adam-evolution : {len(evo_rules)}")
        print(f"Règles dépréciées     : "
              f"{sum(1 for v in fitness_data.values() if v.get('deprecated'))}")
        print()

        if evo_rules:
            print(f"{'ID':<35} {'Pattern':<30} {'Fitness':<10} {'Occ':<5} {'Dépr'}")
            print(f"{'-'*35} {'-'*30} {'-'*10} {'-'*5} {'-'*5}")
            for rule in evo_rules:
                rid = rule["id"]
                fit = fitness_data.get(rid, {})
                score = fit.get("score", rule.get("fitness_score", 1.0))
                occ = rule.get("occurrences", 0)
                dep = "⚠️" if fit.get("deprecated") else "✅"
                pattern = rule.get("pattern", "")[:30]
                print(f"{rid:<35} {pattern:<30} {score:<10.2f} {occ:<5} {dep}")
        else:
            print("(Aucune règle adam-evolution pour le moment)")

        print()
        return 0


# ─── CLI ────────────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(
        description="ADAM-EVOLUTION — Agent d'évolution des règles Praetor"
    )
    parser.add_argument(
        "--once", action="store_true",
        help="Exécute un seul cycle puis quitte"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Simulation — aucune écriture sur disque"
    )
    parser.add_argument(
        "--status", action="store_true",
        help="Affiche l'état des règles et quitte"
    )
    parser.add_argument(
        "--debug", action="store_true",
        help="Active les logs de debug"
    )
    parser.add_argument(
        "--scan-code", action="store_true",
        help="Scanne le code source (complexité, duplication, dead code, factorisation) puis quitte"
    )
    parser.add_argument(
        "--scan-dir", type=str, default="",
        help="Répertoire à scanner (avec --scan-code). Défaut: eva-adam-v2/"
    )
    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    if args.status:
        return AdamEvolution().status()

    if args.scan_code:
        agent = AdamEvolution(dry_run=args.dry_run)
        report = agent.scan_code(root_dir=args.scan_dir)
        # Affichage formaté
        s = report.get("summary", {})
        print(f"\n{'='*70}")
        print(f"ADAM-EVOLUTION — Rapport d'analyse de code")
        print(f"{'='*70}")
        print(f"Fichiers scannés  : {report.get('files_scanned', 0)}")
        print(f"Lignes totales    : {report.get('total_lines', 0)}")
        print(f"Findings totaux   : {s.get('total', 0)}")
        print(f"  🔴 Critiques     : {s.get('critical', 0)}")
        print(f"  🟡 Warnings      : {s.get('warning', 0)}")
        print(f"  🔵 Info          : {s.get('info', 0)}")
        if s.get("by_type"):
            print(f"\nPar type:")
            for t, count in sorted(s["by_type"].items(), key=lambda x: -x[1]):
                print(f"  {t:<25} {count}")
        findings = report.get("findings", [])
        if findings:
            print(f"\n{'-'*70}")
            print("Détails (50 premiers):")
            print(f"{'-'*70}")
            for f in findings[:50]:
                sev_icon = {"critical": "🔴", "warning": "🟡", "info": "🔵"}.get(
                    f.get("severity", ""), "  "
                )
                print(
                    f"  {sev_icon} [{f.get('type', '?'):<20}] "
                    f"{f.get('file', '?')}:{f.get('line', 0)} — "
                    f"{f.get('message', '')[:80]}"
                )
                if f.get("suggestion"):
                    print(f"      → {f['suggestion'][:80]}")
        print()
        return 0

    agent = AdamEvolution(dry_run=args.dry_run, once=args.once)
    return agent.run()


if __name__ == "__main__":
    sys.exit(main())
