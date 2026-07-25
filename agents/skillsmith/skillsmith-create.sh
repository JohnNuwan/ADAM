#!/usr/bin/env bash
# ===================================================================
# skillsmith-create.sh — Handler ADAM-SKILLSMITH
# Crée automatiquement un SKILL.md quand un événement arrive sur
# research:opportunity ou skill:request.
# ===================================================================

set -uo pipefail

CHANNEL="${ADAM_EVENT_CHANNEL:-unknown}"
PAYLOAD="${ADAM_EVENT_PAYLOAD:-}"
if [ -z "$PAYLOAD" ]; then PAYLOAD='{}'; fi
SOURCE="${ADAM_EVENT_SOURCE:-unknown}"
ADAM_V2_DIR="${ADAM_V2_DIR:-/home/aza/eva-adam-v2}"
SKILLS_DIR="${HOME}/.hermes/skills"
LOG_FILE="${ADAM_V2_DIR}/logs/skillsmith.log"
TIMESTAMP=$(date -Iseconds)

mkdir -p "$(dirname "$LOG_FILE")" "$SKILLS_DIR"

log() {
    echo "[${TIMESTAMP}] [${1:-INFO}] ${2:-}" >> "$LOG_FILE"
}

# Extraire un champ du payload JSON
extract() {
    local key="$1"
    local default="${2:-}"
    echo "$PAYLOAD" | ADAM_KEY="$key" python3 -c '
import json, sys, os
try:
    raw = sys.stdin.read().strip()
    d = json.loads(raw)
    val = d.get(os.environ.get("ADAM_KEY", ""), "")
    print(val)
except Exception:
    print("")
' 2>/dev/null || echo "$default"
}

# Publier un événement sur le Go Bus
publish() {
    local ch="$1" pl="$2"
    local body
    body=$(ADAM_CH="$ch" ADAM_PL="$pl" python3 -c '
import json, os
msg = {
    "topic": os.environ["ADAM_CH"],
    "source": "adam-skillsmith",
    "priority": 5,
    "payload": json.loads(os.environ["ADAM_PL"])
}
print(json.dumps(msg))
' 2>/dev/null)
    curl -s -X POST http://localhost:8086/api/publish \
        -H 'Content-Type: application/json' \
        -d "$body" 2>/dev/null
}

log "INFO" "Channel=$CHANNEL Source=$SOURCE"

# Extraire les infos du payload
SKILL_NAME=$(extract "skill_name" "$(extract "name" "")")
SKILL_CATEGORY=$(extract "category" "$(extract "domain" "general")")
SKILL_DESC=$(extract "description" "$(extract "summary" "")")
SKILL_TAGS=$(extract "tags" "")
PROJECT_URL=$(extract "url" "$(extract "repo" "")")
ARXIV_ID=$(extract "arxiv_id" "")
PAPER_TITLE=$(extract "title" "")

# Nettoyer le nom du skill (lowercase, hyphens)
SKILL_NAME=$(echo "$SKILL_NAME" | tr '[:upper:]' '[:lower:]' | tr ' _' '--' | sed 's/[^a-z0-9-]//g' | head -c 64)

if [ -z "$SKILL_NAME" ]; then
    log "WARN" "Pas de nom de skill dans le payload — abandon"
    echo "skillsmith: no skill name"
    exit 0
fi

SKILL_DIR="${SKILLS_DIR}/${SKILL_CATEGORY}/${SKILL_NAME}"
SKILL_FILE="${SKILL_DIR}/SKILL.md"

log "INFO" "Création skill: ${SKILL_CATEGORY}/${SKILL_NAME}"

# Vérifier si le skill existe déjà
if [ -f "$SKILL_FILE" ]; then
    log "INFO" "Skill ${SKILL_NAME} existe déjà — skip"
    echo "skillsmith: already exists"
    exit 0
fi

mkdir -p "$SKILL_DIR"

# Construire le contenu SKILL.md
cat > "$SKILL_FILE" <<SKILLEOF
---
name: ${SKILL_NAME}
description: ${SKILL_DESC:-Skill auto-généré par ADAM-SKILLSMITH}
category: ${SKILL_CATEGORY}
tags: [${SKILL_TAGS}]
author: adam-skillsmith
created: ${TIMESTAMP}
source: ${SOURCE}
---

# ${SKILL_NAME}

> Auto-généré par **ADAM-SKILLSMITH** le ${TIMESTAMP}
> Source: ${CHANNEL} depuis ${SOURCE}

## Contexte

$([ -n "$PAPER_TITLE" ] && echo "**Paper:** ${PAPER_TITLE}")
$([ -n "$ARXIV_ID" ] && echo "**arXiv:** ${ARXIV_ID}")
$([ -n "$PROJECT_URL" ] && echo "**URL:** ${PROJECT_URL}")

## Description

${SKILL_DESC:-Ce skill a été créé automatiquement à partir d'une opportunité de recherche.}

## Objectifs

1. Comprendre le domaine et les concepts clés
2. Identifier les outils et frameworks pertinents
3. Définir un workflow opérationnel pour The Hive

## Prérequis

- Python 3.11+
- Accès au terminal

## Workflow

*(À compléter par EVA ou un sous-agent)*

## Références

- [Source](${PROJECT_URL:-N/A})
- [EVA/Adam Repository](https://github.com/JohnNuwan/EVA_CORE)

---

*Skill auto-généré par ADAM-SKILLSMITH — The Hive*
SKILLEOF

log "INFO" "Skill créé: ${SKILL_FILE} ($(wc -c < "$SKILL_FILE") octets)"

# Publier l'événement skill:created
RESULT="{\"skill_name\":\"${SKILL_NAME}\",\"category\":\"${SKILL_CATEGORY}\",\"path\":\"${SKILL_FILE}\",\"action\":\"created\",\"source_agent\":\"adam-skillsmith\",\"timestamp\":\"${TIMESTAMP}\"}"
publish "skill:created" "$RESULT"
log "INFO" "Événement skill:created publié"

echo "skillsmith: created ${SKILL_NAME}"
exit 0
