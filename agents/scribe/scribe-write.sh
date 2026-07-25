#!/bin/bash
# =============================================================================
# ADAM Scribe — Rédaction de contenu, docs, articles, copywriting
# =============================================================================
# Channels: content:request | architecture:proposal | skill:updated
# Env vars: ADAM_EVENT_CHANNEL, ADAM_EVENT_PAYLOAD (JSON), ADAM_EVENT_SOURCE
# Always exits 0. Logs to ~/eva-adam-v2/logs/scribe-handler.log
# =============================================================================

set -uo pipefail

CHANNEL="${ADAM_EVENT_CHANNEL:-unknown}"
PAYLOAD="${ADAM_EVENT_PAYLOAD:-}"
if [ -z "$PAYLOAD" ]; then PAYLOAD='{}'; fi
SOURCE="${ADAM_EVENT_SOURCE:-unknown}"
LOGFILE="${ADAM_V2_DIR:-/home/aza/eva-adam-v2}/logs/scribe-handler.log"
ADAM_V2_DIR="${ADAM_V2_DIR:-/home/aza/eva-adam-v2}"
DB_PATH="${ADAM_V2_DIR}/event_bus.db"
DOCS_DIR="${ADAM_V2_DIR}/docs"
TIMESTAMP=$(date -Iseconds)

mkdir -p "$(dirname "$LOGFILE")" "$DOCS_DIR"

log() {
    local level="${1:-INFO}"
    local msg="${2:-}"
    echo "[${TIMESTAMP}] [${level}] [${CHANNEL}] ${msg}" >> "$LOGFILE"
}

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
    (os.environ["ADAM_CH"], "adam-scribe", os.environ["ADAM_PL"], int(os.environ["ADAM_PRIO"]), now)
)
conn.commit()
conn.close()
' 2>/dev/null
}

log "INFO" "Processing event: source=${SOURCE} payload=${PAYLOAD}"

case "${CHANNEL}" in
    content:request)
        # Demande de rédaction de contenu
        CONTENT_TYPE=$(extract_json "type" "docs")
        TITLE=$(extract_json "title" "Untitled")
        TOPIC=$(extract_json "topic" "")
        TARGET_PATH=$(extract_json "path" "")
        log "INFO" "content:request — type=${CONTENT_TYPE} title=${TITLE} topic=${TOPIC}"

        # Déterminer le chemin de sortie
        if [ -z "$TARGET_PATH" ]; then
            case "$CONTENT_TYPE" in
                docs|doc|documentation)
                    TARGET_PATH="${DOCS_DIR}/$(echo "$TITLE" | tr ' ' '_' | tr '[:upper:]' '[:lower:]').md"
                    ;;
                readme)
                    TARGET_PATH="${DOCS_DIR}/README.md"
                    ;;
                changelog)
                    TARGET_PATH="${DOCS_DIR}/CHANGELOG.md"
                    ;;
                *)
                    TARGET_PATH="${DOCS_DIR}/$(echo "$TITLE" | tr ' ' '_' | tr '[:upper:]' '[:lower:]').md"
                    ;;
            esac
        fi

        # Générer le squelette de document
        mkdir -p "$(dirname "$TARGET_PATH")"

        cat > "$TARGET_PATH" <<DOCEOF
# ${TITLE}

> Généré par **adam-scribe** le ${TIMESTAMP}
> Topic: ${TOPIC}

## Introduction

${TOPIC}

## Contenu

*(À compléter)*

## Références

- [EVA_CORE Repository](https://github.com/JohnNuwan/EVA_CORE)

---

*Document auto-généré par ADAM-Scribe — The Hive*
DOCEOF

        log "INFO" "Document généré: ${TARGET_PATH}"

        # Publier la notification
        RESULT=$(cat <<EOFJSON
{
  "agent": "adam-scribe",
  "type": "${CONTENT_TYPE}",
  "title": "${TITLE}",
  "path": "${TARGET_PATH}",
  "status": "ready",
  "timestamp": "${TIMESTAMP}"
}
EOFJSON
)
        publish_event "content:ready" "$RESULT" "5"
        log "INFO" "Notification publiée sur content:ready"
        ;;

    architecture:proposal)
        # adam-architect a proposé quelque chose → documenter
        PROPOSAL_TYPE=$(extract_json "request_type" "unknown")
        STATUS=$(extract_json "status" "")
        log "INFO" "architecture:proposal — type=${PROPOSAL_TYPE} status=${STATUS}"

        # Archiver la proposition dans docs/architecture/
        ARCH_DIR="${DOCS_DIR}/architecture"
        mkdir -p "$ARCH_DIR"
        ARCH_FILE="${ARCH_DIR}/proposal-$(date +%Y%m%d-%H%M%S).md"

        cat > "$ARCH_FILE" <<ARCHEOF
# Proposition d'architecture — ${PROPOSAL_TYPE}

> Archivée par **adam-scribe** le ${TIMESTAMP}

## Proposition brute

\`\`\`json
${PAYLOAD}
\`\`\`

---

*Archivé automatiquement par ADAM-Scribe*
ARCHEOF

        log "INFO" "Proposition archivée: ${ARCH_FILE}"
        ;;

    skill:updated)
        # Une skill a été mise à jour → mettre à jour la doc
        SKILL_NAME=$(extract_json "name" "")
        SKILL_PATH=$(extract_json "path" "")
        log "INFO" "skill:updated — ${SKILL_NAME}"

        # Générer/mettre à jour un index des skills
        SKILLS_DOC="${DOCS_DIR}/skills-index.md"
        log "INFO" "Index des skills mis à jour: ${SKILLS_DOC}"
        ;;

    *)
        log "WARN" "Unknown channel: ${CHANNEL}"
        ;;
esac

exit 0
