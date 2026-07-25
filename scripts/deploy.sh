#!/bin/bash
# ────────────────────────────────────────────────────────────
# EVA ADAM v2 — Handler de déploiement (Levier 3)
# ────────────────────────────────────────────────────────────
# Appelé par event_daemon.py quand un événement arrive sur
# le canal 'hardware:disk_alert' ou 'service:down'.
#
# Variables d'environnement :
#   ADAM_EVENT_CHANNEL  — hardware:disk_alert | service:down
#   ADAM_EVENT_PAYLOAD  — JSON (ex: {"service":"ollama"})
#   ADAM_EVENT_SOURCE   — Source de l'événement
#   ADAM_V2_DIR         — Répertoire base d'ADAM v2
#
# Arguments :
#   --cleanup   — Nettoyage disque (logs, WAL, /tmp/adam-*)
#   --restart   — Redémarrage de service depuis le payload
#
# Toujours exit 0. Timeout: 30s max.
# ────────────────────────────────────────────────────────────

set -euo pipefail

# ── Configuration ──────────────────────────────────────────
ADAM_V2_DIR="${ADAM_V2_DIR:-/home/aza/eva-adam-v2}"
LOGFILE="${ADAM_V2_DIR}/logs/deploy-handler.log"
CHANNEL="${ADAM_EVENT_CHANNEL:-unknown}"
PAYLOAD="${ADAM_EVENT_PAYLOAD:-}"
SOURCE="${ADAM_EVENT_SOURCE:-unknown}"

# Si PAYLOAD est vide, initialiser à {} — évite le bug de parsing
# des accolades dans ${var:-default} (bash interprète mal {{}})
[ -z "$PAYLOAD" ] && PAYLOAD='{}'
SCRIPT_NAME="$(basename "$0")"
TIMEOUT_CMD="timeout 25"

# S'assurer que le répertoire de logs existe
mkdir -p "$(dirname "$LOGFILE")"

# ── Fonctions utilitaires ─────────────────────────────────

log() {
    local level="${1:-INFO}"
    shift
    echo "[$(date -Iseconds)] [${level}] [${SCRIPT_NAME}] $*" >> "$LOGFILE"
}

log_info()  { log "INFO"  "$*"; }
log_warn()  { log "WARN"  "$*"; }
log_error() { log "ERROR" "$*"; }

# Extraire une valeur d'un JSON simple (sans jq)
# Usage: json_get_key '{"service":"ollama"}' service
json_get_key() {
    local json="$1"
    local key="$2"
    echo "$json" | python3 -c "
import sys, json
try:
    data = json.loads(sys.stdin.read())
    print(data.get('$key', ''))
except Exception:
    print('')
" 2>/dev/null || echo ""
}

# Vérifier si un service systemd existe
# Utilise 'systemctl cat' au lieu de pipe+grep pour éviter SIGPIPE
# avec set -o pipefail (grep -q ferme le pipe, systemctl reçoit SIGPIPE → exit 141)
systemd_service_exists() {
    local svc="$1"
    systemctl cat "${svc}.service" 2>/dev/null &>/dev/null && return 0
    return 1
}

systemd_service_is_running() {
    local svc="$1"
    systemctl is-active --quiet "${svc}.service" 2>/dev/null && return 0
    return 1
}

# Redémarrer un service connu non-systemd
restart_known_process() {
    local name="$1"
    case "$name" in
        vllm)
            log_info "Redémarrage de vllm via le stack RAG..."
            if [ -x "/home/aza/rag-stack/start.sh" ]; then
                cd /home/aza/rag-stack
                $TIMEOUT_CMD bash start.sh --background 2>&1 | while IFS= read -r line; do log_info "vllm: $line"; done
                log_info "RAG stack relancé (vllm géré par le script)"
                return 0
            else
                log_warn "Aucun script de démarrage trouvé pour vllm"
                return 1
            fi
            ;;
        *)
            log_error "Processus non-systemd inconnu: $name — aucune procédure de redémarrage"
            return 1
            ;;
    esac
}

# ── Nettoyage ──────────────────────────────────────────────

do_cleanup() {
    log_info "=== DÉBUT NETTOYAGE (disk_alert) ==="
    local freed_bytes=0
    local before after

    # Capturer l'état disque avant
    before=$(df -h / 2>/dev/null | tail -1)

    # ── 1. Logs de plus de 7 jours dans ADAM_V2_DIR/logs/
    local log_dir="${ADAM_V2_DIR}/logs"
    if [ -d "$log_dir" ]; then
        log_info "Nettoyage des logs >7j dans ${log_dir}..."
        local old_logs
        old_logs=$(find "$log_dir" -maxdepth 1 -name '*.log' -type f -mtime +7 -print 2>/dev/null)
        if [ -n "$old_logs" ]; then
            while IFS= read -r f; do
                local sz
                sz=$(stat -c%s "$f" 2>/dev/null || echo 0)
                rm -f "$f"
                freed_bytes=$((freed_bytes + sz))
                log_info "  Supprimé: $(basename "$f") ($((sz)) bytes)"
            done <<< "$old_logs"
        else
            log_info "  Aucun log >7j à nettoyer"
        fi

        # Rotation des logs de l'auto-guérison (self_heal.log.N) — garder les 5 plus récents
        log_info "Rotation des logs self_heal.log.old (max 5 archives)..."
        ls -1 "$log_dir"/self_heal.log.* 2>/dev/null | sort -t. -k3 -n | head -n -5 | while IFS= read -r f; do
            local sz
            sz=$(stat -c%s "$f" 2>/dev/null || echo 0)
            rm -f "$f"
            freed_bytes=$((freed_bytes + sz))
            log_info "  Rotation supprimée: $(basename "$f") ($((sz)) bytes)"
        done
    else
        log_warn "Répertoire de logs inexistant: ${log_dir}"
    fi

    # ── 2. WAL / journal files de SQLite
    log_info "Nettoyage des fichiers WAL/SHM de event_bus.db..."
    for ext in wal shm; do
        local f="${ADAM_V2_DIR}/event_bus.db-${ext}"
        if [ -f "$f" ]; then
            local sz
            sz=$(stat -c%s "$f" 2>/dev/null || echo 0)
            rm -f "$f"
            freed_bytes=$((freed_bytes + sz))
            log_info "  Supprimé: event_bus.db-${ext} ($((sz)) bytes)"
        fi
    done

    # ── 3. Checkpoint du WAL dans la DB (compresser l'espace)
    log_info "Checkpoint WAL sur event_bus.db..."
    if [ -f "${ADAM_V2_DIR}/event_bus.db" ]; then
        python3 -c "
import sqlite3, os
db_path = '${ADAM_V2_DIR}/event_bus.db'
try:
    conn = sqlite3.connect(db_path)
    conn.execute('PRAGMA wal_checkpoint(TRUNCATE);')
    conn.execute('PRAGMA journal_mode=DELETE;')
    conn.execute('VACUUM;')
    conn.close()
    print('DB checkpoint + VACUUM réussi')
except Exception as e:
    print(f'DB checkpoint ignoré: {e}')
" 2>&1 | while IFS= read -r line; do log_info "sqlite: $line"; done
    fi

    # ── 4. Fichiers temporaires /tmp/adam-*
    log_info "Nettoyage des fichiers /tmp/adam-*..."
    local tmp_count=0
    while IFS= read -r f; do
        local sz
        sz=$(stat -c%s "$f" 2>/dev/null || echo 0)
        rm -f "$f"
        freed_bytes=$((freed_bytes + sz))
        tmp_count=$((tmp_count + 1))
    done < <(find /tmp -maxdepth 1 -name 'adam-*' -type f -mtime +1 -print 2>/dev/null)
    log_info "  ${tmp_count} fichier(s) temporaire(s) supprimé(s)"

    # ── 5. Afficher l'impact
    after=$(df -h / 2>/dev/null | tail -1)
    local freed_mb=$((freed_bytes / 1048576))
    log_info "=== NETTOYAGE TERMINÉ ==="
    log_info "Espace libéré: ${freed_mb} MB (${freed_bytes} bytes)"
    log_info "Avant: ${before}"
    log_info "Après: ${after}"
}

# ── Redémarrage ────────────────────────────────────────────

do_restart() {
    log_info "=== DÉBUT REDÉMARRAGE (service:down) ==="

    local service_name
    service_name=$(json_get_key "$PAYLOAD" "service")

    if [ -z "$service_name" ]; then
        log_error "Payload JSON ne contient pas de champ 'service': ${PAYLOAD}"
        log_info "=== REDÉMARRAGE ABANDONNÉ (pas de service) ==="
        return
    fi

    log_info "Service cible: ${service_name} (source: ${SOURCE})"

    # ── Vérification : pas de redémarrage système critique
    local critical_services=("reboot" "shutdown" "halt" "poweroff" "systemd" "dbus" "ssh" "sshd")
    for cs in "${critical_services[@]}"; do
        if [[ "$service_name" == "$cs" ]]; then
            log_warn "REFUS: ${service_name} est un service système critique — pas de redémarrage"
            log_info "=== REDÉMARRAGE REFUSÉ (service critique) ==="
            return
        fi
    done

    # ── Essai systemd d'abord
    if systemd_service_exists "$service_name"; then
        log_info "Service systemd détecté: ${service_name}"
        local was_running=false
        if systemd_service_is_running "$service_name"; then
            was_running=true
            log_info "État actuel: running"
        else
            log_info "État actuel: stopped/inactive"
        fi

        log_info "Exécution: systemctl restart ${service_name}.service..."
        if $TIMEOUT_CMD systemctl restart "${service_name}.service" 2>&1; then
            log_info "systemctl restart réussi pour ${service_name}"
            sleep 2
            if systemd_service_is_running "$service_name"; then
                log_info "✅ Service ${service_name} redémarré et opérationnel"
            else
                log_warn "⚠️  Service ${service_name} redémarré mais ne répond pas encore"
            fi
        else
            log_error "systemctl restart a échoué pour ${service_name} (code: $?)"
            log_warn "Tentative: systemctl start ${service_name}.service..."
            $TIMEOUT_CMD systemctl start "${service_name}.service" 2>&1 || log_error "systemctl start a aussi échoué"
        fi
    else
        # ── Service non-systemd : essayer les procédures connues
        log_info "Service non-systemd: ${service_name} — tentative via procédure personnalisée"
        restart_known_process "$service_name" || log_warn "Aucune procédure de redémarrage connue pour ${service_name}"
    fi

    log_info "=== REDÉMARRAGE TERMINÉ ==="
}

# ── Point d'entrée ─────────────────────────────────────────

# Log de l'appel
log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log_info "Appel reçu | channel=${CHANNEL} source=${SOURCE} args=$*"
log_info "Payload: ${PAYLOAD}"

# Exécution selon l'argument
if [[ "$*" == *"--cleanup"* ]]; then
    do_cleanup
elif [[ "$*" == *"--restart"* ]]; then
    do_restart
else
    log_warn "Aucun argument reconnu — utilisation: $0 [--cleanup|--restart]"
    log_info "Usage:"
    log_info "  --cleanup   Nettoyer logs anciens, WAL, /tmp/adam-*"
    log_info "  --restart   Redémarrer un service depuis ADAM_EVENT_PAYLOAD.service"
fi

log_info "Terminé (exit 0)"
exit 0