#!/bin/bash
# =============================================================================
# ADAM Architect — Conception de logiciels, architectures et systèmes autonomes
# =============================================================================
# Channels: architecture:request | evolution:code_review | skill:created
# Env vars: ADAM_EVENT_CHANNEL, ADAM_EVENT_PAYLOAD (JSON), ADAM_EVENT_SOURCE
# Always exits 0. Logs to ~/eva-adam-v2/logs/architect-handler.log
# =============================================================================

set -uo pipefail

CHANNEL="${ADAM_EVENT_CHANNEL:-unknown}"
PAYLOAD="${ADAM_EVENT_PAYLOAD:-}"
if [ -z "$PAYLOAD" ]; then PAYLOAD='{}'; fi
SOURCE="${ADAM_EVENT_SOURCE:-unknown}"
LOGFILE="${ADAM_V2_DIR:-/home/aza/eva-adam-v2}/logs/architect-handler.log"
ADAM_V2_DIR="${ADAM_V2_DIR:-/home/aza/eva-adam-v2}"
DB_PATH="${ADAM_V2_DIR}/event_bus.db"
TIMESTAMP=$(date -Iseconds)

mkdir -p "$(dirname "$LOGFILE")"

log() {
    local level="${1:-INFO}"
    local msg="${2:-}"
    echo "[${TIMESTAMP}] [${level}] [${CHANNEL}] ${msg}" >> "$LOGFILE"
}

# JSON extraction via python3
extract_json() {
    local key="$1"
    local default="${2:-}"
    echo "$PAYLOAD" | ADAM_KEY="$key" python3 -c '
import json, sys, os
try:
    raw = sys.stdin.read().strip()
    while raw and raw.count("{") < raw.count("}"):
        raw = raw.rstrip("}")
    d = json.loads(raw)
    val = d.get(os.environ.get("ADAM_KEY", ""), "")
    print(val)
except Exception:
    print("")
' 2>/dev/null || echo "${2:-}"
}

# Publish an event to the bus
publish_event() {
    local ch="$1"
    local pl="$2"
    local prio="${3:-5}"
    ADAM_CH="$ch" ADAM_PL="$pl" ADAM_PRIO="$prio" python3 -c '
import json, sqlite3, os
from datetime import datetime, timezone
db = os.environ.get("ADAM_V2_DIR", "/home/aza/eva-adam-v2") + "/event_bus.db"
conn = sqlite3.connect(db, timeout=5)
now = datetime.now(timezone.utc).isoformat()
conn.execute(
    "INSERT INTO events (channel, source, payload, status, priority, created_at) "
    "VALUES (?, ?, ?, \"pending\", ?, ?)",
    (os.environ["ADAM_CH"], "adam-architect", os.environ["ADAM_PL"], int(os.environ["ADAM_PRIO"]), now)
)
conn.commit()
conn.close()
' 2>/dev/null
}

log "INFO" "Processing event: source=${SOURCE} payload=${PAYLOAD}"

case "${CHANNEL}" in
    architecture:request)
        # Quelqu'un demande une conception d'architecture
        REQUEST_TYPE=$(extract_json "type" "unknown")
        DESCRIPTION=$(extract_json "description" "")
        TARGET_DIR=$(extract_json "target_dir" "")
        log "INFO" "architecture:request — type=${REQUEST_TYPE} desc=${DESCRIPTION}"

        # Analyser le contexte du projet
        if [ -n "$TARGET_DIR" ] && [ -d "$TARGET_DIR" ]; then
            FILE_COUNT=$(find "$TARGET_DIR" -name "*.py" -not -path "*/venv/*" -not -path "*/__pycache__/*" 2>/dev/null | wc -l)
            TOTAL_LINES=$(find "$TARGET_DIR" -name "*.py" -not -path "*/venv/*" -not -path "*/__pycache__/*" -exec cat {} + 2>/dev/null | wc -l)
            log "INFO" "Project context: ${FILE_COUNT} files, ${TOTAL_LINES} lines"

            # Détecter patterns d'architecture
            HAS_INIT=$(find "$TARGET_DIR" -name "__init__.py" 2>/dev/null | wc -l)
            HAS_SETUP=$(test -f "$TARGET_DIR/setup.py" -o -f "$TARGET_DIR/pyproject.toml" && echo "yes" || echo "no")
            HAS_DOCKER=$(test -f "$TARGET_DIR/Dockerfile" && echo "yes" || echo "no")
            HAS_CI=$(find "$TARGET_DIR" -name ".github" -o -name ".gitlab-ci.yml" 2>/dev/null | head -1 | grep -q . && echo "yes" || echo "no")
            log "INFO" "Patterns: packages=${HAS_INIT} setup=${HAS_SETUP} docker=${HAS_DOCKER} ci=${HAS_CI}"
        else
            FILE_COUNT=0
            TOTAL_LINES=0
        fi

        # Générer une proposition d'architecture
        PROPOSAL=$(cat <<EOFJSON
{
  "agent": "adam-architect",
  "request_type": "${REQUEST_TYPE}",
  "description": "${DESCRIPTION}",
  "analysis": {
    "files": ${FILE_COUNT},
    "lines": ${TOTAL_LINES}
  },
  "recommendations": [
    "Modulariser en packages avec __init__.py",
    "Ajouter pyproject.toml pour packaging",
    "Dockerfile multi-stage pour reproductibilité",
    "Tests unitaires avec pytest + coverage"
  ],
  "status": "proposed",
  "timestamp": "${TIMESTAMP}"
}
EOFJSON
)
        publish_event "architecture:proposal" "$PROPOSAL" "5"
        log "INFO" "Proposition d'architecture publiée sur architecture:proposal"
        ;;

    evolution:code_review)
        # adam-evolution a trouvé des issues → proposer des refactors
        FINDINGS_COUNT=$(extract_json "findings_count" "0")
        CRITICAL=$(extract_json "critical" "0")
        log "INFO" "evolution:code_review — ${FINDINGS_COUNT} findings (${CRITICAL} critiques)"

        if [ "$CRITICAL" -gt 0 ] 2>/dev/null; then
            # Proposer un plan de refactor pour les issues critiques
            REFACTOR_PROPOSAL=$(cat <<EOFJSON
{
  "agent": "adam-architect",
  "trigger": "evolution:code_review",
  "critical_findings": ${CRITICAL},
  "action": "refactor_needed",
  "proposal": "Refactor des sections avec complexité élevée et dead code",
  "status": "proposed",
  "timestamp": "${TIMESTAMP}"
}
EOFJSON
)
            publish_event "architecture:proposal" "$REFACTOR_PROPOSAL" "8"
            log "INFO" "Plan de refactor publié (priorité haute — ${CRITICAL} critiques)"
        else
            log "INFO" "Pas de findings critiques, pas de refactor nécessaire"
        fi
        ;;

    skill:created)
        # Une nouvelle skill a été créée → valider l'architecture
        SKILL_NAME=$(extract_json "name" "")
        SKILL_PATH=$(extract_json "path" "")
        log "INFO" "skill:created — ${SKILL_NAME} à ${SKILL_PATH}"

        if [ -n "$SKILL_PATH" ] && [ -f "$SKILL_PATH" ]; then
            # Vérifier la structure de la skill
            SKILL_DIR=$(dirname "$SKILL_PATH")
            HAS_REFERENCES=$(test -d "$SKILL_DIR/references" && echo "yes" || echo "no")
            HAS_TEMPLATES=$(test -d "$SKILL_DIR/templates" && echo "yes" || echo "no")
            HAS_SCRIPTS=$(test -d "$SKILL_DIR/scripts" && echo "yes" || echo "no")
            log "INFO" "Skill structure: references=${HAS_REFERENCES} templates=${HAS_TEMPLATES} scripts=${HAS_SCRIPTS}"

            # Publier feedback
            FEEDBACK=$(cat <<EOFJSON
{
  "agent": "adam-architect",
  "skill": "${SKILL_NAME}",
  "structure": {
    "references": "${HAS_REFERENCES}",
    "templates": "${HAS_TEMPLATES}",
    "scripts": "${HAS_SCRIPTS}"
  },
  "status": "reviewed",
  "timestamp": "${TIMESTAMP}"
}
EOFJSON
)
            publish_event "architecture:proposal" "$FEEDBACK" "3"
        fi
        ;;

    *)
        log "WARN" "Unknown channel: ${CHANNEL}"
        ;;
esac

exit 0
