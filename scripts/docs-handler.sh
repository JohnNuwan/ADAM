#!/usr/bin/env bash
# ===================================================================
# docs-handler.sh — Handler ADAM v2 pour adam-docs
# Canal: wiki:update
# Reçoit les notifications de adam-critic (skill:updated/created/broken)
# et génère/met à jour la documentation du wiki.
# ===================================================================

CHANNEL="${ADAM_EVENT_CHANNEL:-unknown}"
PAYLOAD="${ADAM_EVENT_PAYLOAD:-}"
if [ -z "$PAYLOAD" ]; then PAYLOAD='{}'; fi
SOURCE="${ADAM_EVENT_SOURCE:-unknown}"
ARG="$1"

ADAM_V2_DIR="${ADAM_V2_DIR:-/home/aza/eva-adam-v2}"
LOG_DIR="$ADAM_V2_DIR/logs"
LOG_FILE="$LOG_DIR/docs-handler.log"
WIKI_DIR="${ADAM_V2_DIR}/docs/wiki"
SKILLS_DIR="${HOME}/.hermes/skills"

mkdir -p "$LOG_DIR" "$WIKI_DIR"

# Parser le payload
SKILL_NAME=$(echo "$PAYLOAD" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('skill_name',d.get('skill','')))" 2>/dev/null)
ACTION=$(echo "$PAYLOAD" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('action',''))" 2>/dev/null)
SOURCE_AGENT=$(echo "$PAYLOAD" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('source_agent',''))" 2>/dev/null)

TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

log() {
    echo "[$TIMESTAMP] [docs] $1" >> "$LOG_FILE"
}

log "Canal: $CHANNEL | Source: $SOURCE | Skill: $SKILL_NAME | Action: $ACTION"

# Trouver le fichier SKILL.md si un skill est mentionné
if [ -n "$SKILL_NAME" ] && [ "$SKILL_NAME" != "" ]; then
    SKILL_FILE=$(find "$SKILLS_DIR" -name "SKILL.md" -path "*${SKILL_NAME}*" 2>/dev/null | head -1)
    if [ -n "$SKILL_FILE" ]; then
        SKILL_SIZE=$(wc -c < "$SKILL_FILE" 2>/dev/null || echo "0")
        log "Skill trouvé: $SKILL_FILE ($SKILL_SIZE octets)"
    else
        log "⚠ Skill non trouvé: $SKILL_NAME"
    fi
fi

# Mettre à jour l'index du wiki
INDEX_FILE="$WIKI_DIR/INDEX.md"

{
    echo "# 📚 Wiki E.V.A — Index Auto-Généré"
    echo ""
    echo "> Dernière mise à jour: $(date -u +'%Y-%m-%d %H:%M:%S UTC')"
    echo "> Source: adam-docs (déclenché par $SOURCE_AGENT)"
    echo ""

    # Lister les skills disponibles
    if [ -d "$SKILLS_DIR" ]; then
        SKILL_COUNT=$(find "$SKILLS_DIR" -name "SKILL.md" 2>/dev/null | wc -l)
        echo "## 🧠 Skills ($SKILL_COUNT)"
        echo ""
        find "$SKILLS_DIR" -name "SKILL.md" -printf "%h\n" 2>/dev/null | \
            sed "s|$SKILLS_DIR/||" | sort | while read -r skill_dir; do
            echo "- [[$skill_dir]]"
        done
        echo ""
    fi

    # Lister les pages du wiki
    if [ -d "$WIKI_DIR" ]; then
        PAGE_COUNT=$(find "$WIKI_DIR" -name "*.md" ! -name "INDEX.md" 2>/dev/null | wc -l)
        echo "## 📄 Pages Wiki ($PAGE_COUNT)"
        echo ""
        find "$WIKI_DIR" -name "*.md" ! -name "INDEX.md" -printf "%f\n" 2>/dev/null | sort | while read -r page; do
            echo "- [[$page]]"
        done
    fi

} > "$INDEX_FILE"

log "Index wiki mis à jour: $INDEX_FILE"

# Loguer l'événement de skill si applicable
if [ -n "$SKILL_NAME" ] && [ -n "$ACTION" ]; then
    SKILL_LOG="$WIKI_DIR/SKILL_CHANGES.md"
    {
        echo "| $(date -u +'%Y-%m-%d %H:%M:%S') | $SKILL_NAME | $ACTION | $SOURCE_AGENT |"
    } >> "$SKILL_LOG" 2>/dev/null
    log "Changement de skill journalisé: $SKILL_NAME ($ACTION)"
fi

log "Traitement terminé — wiki:update traité avec succès"
echo "docs-handler: done"
