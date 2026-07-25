#!/bin/bash
# critic-review.sh — Handler ADAM v2 pour adam-critic
# Canaux: skill:broken, skill:created, skill:updated
# Argument optionnel: --fix (pour skill:broken)

CHANNEL="${ADAM_EVENT_CHANNEL:-unknown}"
PAYLOAD="${ADAM_EVENT_PAYLOAD:-}"
if [ -z "$PAYLOAD" ]; then PAYLOAD='{}'; fi
SOURCE="${ADAM_EVENT_SOURCE:-unknown}"
ARG="$1"
LOG_DIR="${ADAM_V2_DIR:-/home/aza/eva-adam-v2}/logs"
LOG_FILE="$LOG_DIR/critic-handler.log"
SKILLS_DIR="${HOME}/.hermes/skills"

mkdir -p "$LOG_DIR"

# Parser le payload avec python3
SKILL_NAME=$(echo "$PAYLOAD" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('skill_name',d.get('skill','')))" 2>/dev/null)
SKILL_PATH=$(echo "$PAYLOAD" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('path',''))" 2>/dev/null)
SKILL_ERROR=$(echo "$PAYLOAD" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('error',''))" 2>/dev/null)

TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

log() {
    echo "[$TIMESTAMP] [critic] $1" >> "$LOG_FILE"
}

log "Canal: $CHANNEL | Source: $SOURCE | Skill: $SKILL_NAME | Arg: $ARG"

# Déterminer le chemin du SKILL.md
if [ -n "$SKILL_PATH" ] && [ -f "$SKILL_PATH" ]; then
    SKILL_FILE="$SKILL_PATH"
elif [ -n "$SKILL_NAME" ] && [ -f "$SKILLS_DIR/$SKILL_NAME/SKILL.md" ]; then
    SKILL_FILE="$SKILLS_DIR/$SKILL_NAME/SKILL.md"
else
    # Chercher dans tous les skills
    SKILL_FILE=$(find "$SKILLS_DIR" -name "SKILL.md" -path "*$SKILL_NAME*" 2>/dev/null | head -1)
fi

case "$CHANNEL" in
    skill:broken)
        log "Skill cassé: $SKILL_NAME"
        log "Erreur: $SKILL_ERROR"

        if [ -z "$SKILL_FILE" ]; then
            log "⚠ Fichier SKILL.md introuvable pour '$SKILL_NAME'"
            echo "SKILL.md introuvable"
            exit 0
        fi

        log "Fichier: $SKILL_FILE"

        # Valider le YAML frontmatter
        if ! head -1 "$SKILL_FILE" | grep -q "^---"; then
            log "⚠ Pas de YAML frontmatter (---) en début de fichier"
            if [ "$ARG" = "--fix" ]; then
                log "--fix demandé mais impossible de corriger automatiquement un frontmatter manquant"
            fi
        else
            # Extraire et valider le YAML
            YAML_CONTENT=$(sed -n '/^---$/,/^---$/p' "$SKILL_FILE" | head -n -1 | tail -n +2)
            if echo "$YAML_CONTENT" | python3 -c "import sys,yaml; yaml.safe_load(sys.stdin)" 2>/dev/null; then
                log "✓ YAML frontmatter valide"
            else
                log "⚠ YAML frontmatter invalide"
                if [ "$ARG" = "--fix" ]; then
                    log "Tentative de correction: backup + ajout frontmatter minimal"
                    cp "$SKILL_FILE" "${SKILL_FILE}.bak.$(date +%s)"
                    log "Backup créé: ${SKILL_FILE}.bak.$(date +%s)"
                fi
            fi
        fi

        # Vérifier que le fichier n'est pas vide
        SIZE=$(wc -c < "$SKILL_FILE" 2>/dev/null || echo 0)
        if [ "$SIZE" -lt 50 ]; then
            log "⚠ Fichier SKILL.md trop petit ($SIZE octets) — probablement vide ou corrompu"
        fi

        log "Review terminée pour skill:broken"
        ;;

    skill:created)
        log "Nouveau skill détecté: $SKILL_NAME"
        if [ -n "$SKILL_FILE" ]; then
            log "Fichier: $SKILL_FILE"
            SIZE=$(wc -c < "$SKILL_FILE" 2>/dev/null || echo 0)
            log "Taille: $SIZE octets"

            # Valider la structure de base
            if head -1 "$SKILL_FILE" | grep -q "^---"; then
                log "✓ Frontmatter YAML présent"
            else
                log "⚠ Pas de frontmatter YAML"
            fi

            # Compter les sections
            SECTIONS=$(grep -c "^##\|^# " "$SKILL_FILE" 2>/dev/null || echo 0)
            log "Sections détectées: $SECTIONS"
        else
            log "⚠ Fichier SKILL.md introuvable"
        fi
        log "Review terminée pour skill:created"
        ;;

    skill:updated)
        log "Skill mis à jour: $SKILL_NAME"
        if [ -n "$SKILL_FILE" ]; then
            log "Fichier: $SKILL_FILE"
            SIZE=$(wc -c < "$SKILL_FILE" 2>/dev/null || echo 0)
            log "Nouvelle taille: $SIZE octets"

            # Valider le YAML
            if head -1 "$SKILL_FILE" | grep -q "^---"; then
                if sed -n '2,/^---$/p' "$SKILL_FILE" | head -n -1 | python3 -c "import sys,yaml; yaml.safe_load(sys.stdin)" 2>/dev/null; then
                    log "✓ YAML frontmatter valide après mise à jour"
                else
                    log "⚠ YAML frontmatter invalide après mise à jour"
                fi
            fi
        else
            log "⚠ Fichier SKILL.md introuvable pour skill mis à jour"
        fi
        log "Review terminée pour skill:updated"
        ;;

    *)
        log "Canal non reconnu: $CHANNEL"
        ;;
esac

# ──────────────────────────────────────────────
# Follow-up events — chaînes entre agents
# ──────────────────────────────────────────────
PUBLISH="${ADAM_V2_DIR:-/home/aza/eva-adam-v2}/publish.py"

case "$CHANNEL" in
    skill:created|skill:updated)
        # Skill modifié → notifier adam-docs pour màj wiki
        python3 "$PUBLISH" wiki:update "{\"skill\":\"${SKILL_NAME:-unknown}\",\"action\":\"${CHANNEL}\",\"source_agent\":\"adam-critic\"}" --source adam-critic 2>/dev/null
        log "→ published wiki:update for adam-docs"
        ;;
    skill:broken)
        # Skill cassé → notifier adam-praetor pour investigation
        python3 "$PUBLISH" config:changed "{\"component\":\"skill:${SKILL_NAME:-unknown}\",\"type\":\"broken\",\"error\":\"${SKILL_ERROR:-}\",\"source_agent\":\"adam-critic\"}" --source adam-critic 2>/dev/null
        log "→ published config:changed for adam-praetor"
        ;;
esac

echo "critic-review: done"
exit 0
