#!/bin/bash
# sentinel-watch.sh — Handler ADAM v2 pour adam-sentinel
# Canal: update:available

CHANNEL="${ADAM_EVENT_CHANNEL:-unknown}"
PAYLOAD="${ADAM_EVENT_PAYLOAD:-}"
if [ -z "$PAYLOAD" ]; then PAYLOAD='{}'; fi
SOURCE="${ADAM_EVENT_SOURCE:-unknown}"
LOG_DIR="${ADAM_V2_DIR:-/home/aza/eva-adam-v2}/logs"
LOG_FILE="$LOG_DIR/sentinel-handler.log"

mkdir -p "$LOG_DIR"

# Parser le payload
UPDATE_TYPE=$(echo "$PAYLOAD" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('type',''))" 2>/dev/null)
UPDATE_NAME=$(echo "$PAYLOAD" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('name',''))" 2>/dev/null)
UPDATE_VERSION=$(echo "$PAYLOAD" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('version',''))" 2>/dev/null)

TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

log() {
    echo "[$TIMESTAMP] [sentinel] $1" >> "$LOG_FILE"
}

log "Canal: $CHANNEL | Source: $SOURCE | Type: $UPDATE_TYPE | Name: $UPDATE_NAME | Version: $UPDATE_VERSION"

case "$CHANNEL" in
    update:available)
        log "Mise à jour disponible: $UPDATE_NAME v$UPDATE_VERSION (type: $UPDATE_TYPE)"

        # Selon le type de mise à jour, collecter des info
        case "$UPDATE_TYPE" in
            apt|system)
                # Vérifier les MAJ disponibles
                UPGRADABLE=$(apt list --upgradable 2>/dev/null | grep -c "upgradable" || echo 0)
                log "Paquets upgradable: $UPGRADABLE"

                # Lister les updates de sécurité
                SECURITY_UPDATES=$(apt list --upgradable 2>/dev/null | grep -i "security" | head -5)
                if [ -n "$SECURITY_UPDATES" ]; then
                    log "Updates de sécurité:"
                    echo "$SECURITY_UPDATES" | while read -r line; do
                        log "  $line"
                    done
                fi
                ;;

            pip|python)
                # Vérifier les paquets pip
                if [ -d "${HOME}/jepa_eva/venv" ]; then
                    PIP_OUTDATED=$("${HOME}/jepa_eva/venv/bin/pip" list --outdated --format=columns 2>/dev/null | tail -n +3 | head -10)
                    if [ -n "$PIP_OUTDATED" ]; then
                        log "Paquets pip outdated:"
                        echo "$PIP_OUTDATED" | while read -r line; do
                            log "  $line"
                        done
                    fi
                fi
                ;;

            *)
                log "Type de mise à jour non reconnu: $UPDATE_TYPE"
                ;;
        esac

        # Suggérer l'action
        log "Action suggérée: apt update && apt upgrade -y (pour system) ou pip install --upgrade {package} (pour python)"
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
    update:available)
        # MAJ détectée → notifier adam-praetor pour validation config
        python3 "$PUBLISH" config:changed "{\"component\":\"${UPDATE_NAME:-unknown}\",\"type\":\"update_available\",\"version\":\"${UPDATE_VERSION:-}\",\"source_agent\":\"adam-sentinel\"}" --source adam-sentinel 2>/dev/null
        log "→ published config:changed for adam-praetor"
        ;;
    security:alert)
        # Alerte sécurité reçue → notifier adam-red pour recherche OSINT
        python3 "$PUBLISH" security:scan "{\"source\":\"adam-sentinel\",\"alert_type\":\"${UPDATE_TYPE:-generic}\",\"source_agent\":\"adam-sentinel\"}" --source adam-sentinel 2>/dev/null
        log "→ published security:scan for adam-red"
        ;;
esac

echo "sentinel-watch: done"
exit 0
