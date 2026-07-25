#!/usr/bin/env bash
#===============================================================================
# heal-handler.sh — Handler d'auto-guérison pour ADAM v2
#
# Invoqué par event_daemon.py quand un événement 'adam:error' ou
# 'hardware:gpu_alert' est dispatché.
#
# Variables d'environnement fournies par le daemon :
#   ADAM_EVENT_ID       ID de l'événement
#   ADAM_EVENT_CHANNEL  Canal (adam:error, hardware:gpu_alert, ...)
#   ADAM_EVENT_SOURCE   Source de l'événement
#   ADAM_EVENT_PAYLOAD  Payload JSON (contenant error_type, agent_id, ...)
#   ADAM_EVENT_PRIORITY Priorité
#   ADAM_AGENT_ID       Agent ADAM cible
#   ADAM_V2_DIR         Répertoire racine ADAM v2
#
# Codes de sortie :
#   0   = Succès
#   1   = Échec de la résolution
#   2   = Handler inconnu / type d'erreur non géré
#   126 = Erreur d'exécution interne
#   127 = Payload invalide / arguments manquants
#
# Dépendances : bash 4+, curl, systemctl (user), nvidia-smi (optionnel)
#===============================================================================

set -o pipefail
set -o errexit
# Pas de set -u car on teste les variables avant usage

# ─── Configuration ──────────────────────────────────────────────────────────

# Répertoire ADAM v2
ADAM_V2_DIR="${ADAM_V2_DIR:-/home/aza/eva-adam-v2}"

# Logs
LOG_DIR="${ADAM_V2_DIR}/logs"
LOG_FILE="${LOG_DIR}/heal-handler.log"
mkdir -p "${LOG_DIR}"

# Fichier PID pour les daemons
PID_DIR="${ADAM_V2_DIR}/pids"

# Nombre max de tentatives pour les retries
MAX_RETRIES=3
RETRY_DELAY=10

# ─── Fonctions utilitaires ─────────────────────────────────────────────────

# logger "LEVEL" "message"
logger() {
    local level="${1:-INFO}"
    local message="${2:-}"
    local timestamp
    timestamp="$(date --utc '+%Y-%m-%dT%H:%M:%SZ' 2>/dev/null || date -u '+%Y-%m-%dT%H:%M:%SZ')"
    echo "${timestamp} [${level}] heal-handler[$$] — ${message}" >> "${LOG_FILE}"
}

# valide_payload : vérifie que les variables d'env essentielles sont présentes
valide_payload() {
    local code=0

    if [ -z "${ADAM_EVENT_ID:-}" ]; then
        logger "ERROR" "ADAM_EVENT_ID manquant"
        code=127
    fi

    if [ -z "${ADAM_EVENT_CHANNEL:-}" ]; then
        logger "ERROR" "ADAM_EVENT_CHANNEL manquant"
        code=127
    fi

    if [ -z "${ADAM_EVENT_PAYLOAD:-}" ]; then
        logger "ERROR" "ADAM_EVENT_PAYLOAD manquant"
        code=127
    fi

    return "${code}"
}

# extraire_payload : extrait une clé du payload JSON
# Usage : extraire_payload "error_type"
# Utilise jq si disponible (plus robuste), sinon python3
extraire_payload() {
    local key="$1"
    local payload="${ADAM_EVENT_PAYLOAD:-{}}"

    if command -v jq &>/dev/null; then
        echo "${payload}" | jq -r ".${key} // empty" 2>/dev/null || echo ""
    else
        # Fallback python3 — écrire le payload dans un fichier temporaire
        # pour éviter les problèmes de quoting avec les guillemets du JSON
        local tmpfile
        tmpfile="$(mktemp /tmp/adam_heal_XXXXXX.json 2>/dev/null || echo "/dev/null")"
        printf '%s' "${payload}" > "${tmpfile}"
        python3 -c "
import json, sys
try:
    with open('${tmpfile}') as f:
        data = json.load(f)
    val = data.get('${key}', '')
    if val:
        print(val)
except Exception:
    pass
" 2>/dev/null || true
        [ "${tmpfile}" != "/dev/null" ] && rm -f "${tmpfile}"
    fi
}

# verifier_process : vérifie qu'un processus tourne par son nom
# Retourne 0 si le process existe, 1 sinon
verifier_process() {
    local nom="$1"
    pgrep -x "${nom}" >/dev/null 2>&1 && return 0
    return 1
}

# verifier_service_systemd : vérifie qu'un service systemd --user est actif
verifier_service_systemd() {
    local service="$1"
    local state
    state="$(systemctl --user is-active "${service}" 2>/dev/null || true)"
    if [ "${state}" = "active" ]; then
        return 0
    fi
    return 1
}

# verifier_gpu : vérifie l'état GPU (non-bloquant)
verifier_gpu() {
    if command -v nvidia-smi &>/dev/null; then
        local usage
        usage="$(nvidia-smi --query-gpu=memory.used,memory.total \
                 --format=csv,noheader,nounits 2>/dev/null | head -1 || true)"
        if [ -n "${usage}" ]; then
            local used="${usage%%,*}"
            local total="${usage##*, }"
            if [ "${total}" -gt 0 ] 2>/dev/null; then
                local pct=$((used * 100 / total))
                if [ "${pct}" -gt 90 ]; then
                    logger "WARN" "GPU encore saturé : ${pct}% utilisé (${used}/${total} MiB)"
                    return 1
                fi
            fi
        fi
    fi
    return 0
}

# ─── Handlers par type d'erreur ────────────────────────────────────────────

# handle_retry : re-tente l'action qui a échoué
handle_retry() {
    local event_id="${ADAM_EVENT_ID:-(inconnu)}"
    local channel="${ADAM_EVENT_CHANNEL:-}"
    local payload="${ADAM_EVENT_PAYLOAD:-{}}"

    # Compter les tentatives déjà effectuées (stocké dans le payload)
    local retry_count
    retry_count="$(extraire_payload "retry_count")"
    retry_count="${retry_count:-0}"
    retry_count=$((retry_count + 1))

    logger "INFO" "[retry] Event #${event_id} — tentative ${retry_count}/${MAX_RETRIES}"

    if [ "${retry_count}" -gt "${MAX_RETRIES}" ]; then
        logger "ERROR" "[retry] Event #${event_id} — tentatives épuisées (${MAX_RETRIES})"
        return 1
    fi

    # Publier un nouvel événement via le bus SQLite (INSERT direct)
    local now
    now="$(date --utc '+%Y-%m-%dT%H:%M:%SZ' 2>/dev/null || date -u '+%Y-%m-%dT%H:%M:%SZ')"

    # Incrémenter le compteur de retry dans le payload
    local nouveau_payload
    nouveau_payload="$(python3 -c "
import json, sys
try:
    data = json.loads('${payload}')
    data['retry_count'] = ${retry_count}
    data['retry_of'] = ${event_id}
    print(json.dumps(data, ensure_ascii=False))
except:
    print(json.dumps({'retry_count': ${retry_count}, 'retry_of': ${event_id}}))
" 2>/dev/null || echo "{\"retry_count\":${retry_count},\"retry_of\":${event_id}}")"

    # INSERT dans events table (identique à EventBus.publish)
    python3 -c "
import json, sqlite3, sys
try:
    conn = sqlite3.connect('${ADAM_V2_DIR}/event_bus.db', timeout=10)
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute(
        'INSERT INTO events (channel, source, payload, priority, created_at, status) VALUES (?, ?, ?, ?, ?, ?)',
        ('${channel}', 'heal-handler-retry', json.dumps(json.loads('''${nouveau_payload}''')), 0, '${now}', 'pending')
    )
    conn.commit()
    conn.close()
    print('OK')
except Exception as e:
    print(f'FAIL: {e}', file=sys.stderr)
    sys.exit(1)
" 2>/dev/null || true

    logger "INFO" "[retry] Event #${event_id} — tentative ${retry_count} publiée"
    return 0
}

# handle_restart_service : redémarre un service systemd ou processus
handle_restart_service() {
    local event_id="${ADAM_EVENT_ID:-(inconnu)}"
    local service
    service="$(extraire_payload "service")"
    if [ -z "${service}" ]; then
        service="$(extraire_payload "agent_id")"
    fi
    if [ -z "${service}" ]; then
        service="adam-event-daemon"
    fi

    logger "INFO" "[restart_service] Event #${event_id} — tentative de redémarrage de '${service}'"

    # Tentative 1 : systemctl --user
    if command -v systemctl &>/dev/null; then
        if systemctl --user restart "${service}" 2>/dev/null; then
            logger "INFO" "[restart_service] Event #${event_id} — '${service}' redémarré via systemctl"
            sleep 2
            if verifier_service_systemd "${service}"; then
                return 0
            fi
            logger "WARN" "[restart_service] '${service}' redémarré mais pas encore actif"
            return 0
        fi
        logger "WARN" "[restart_service] systemctl --user a échoué pour '${service}'"
    fi

    # Tentative 2 : pkill + relance
    if pkill -x "${service}" 2>/dev/null; then
        sleep 2
        logger "INFO" "[restart_service] Event #${event_id} — '${service}' tué par pkill"
        return 0
    fi

    logger "ERROR" "[restart_service] Event #${event_id} — impossible de redémarrer '${service}'"
    return 1
}

# handle_restart_agent : redémarre un agent ADAM spécifique
handle_restart_agent() {
    local event_id="${ADAM_EVENT_ID:-(inconnu)}"
    local agent_id
    agent_id="$(extraire_payload "agent_id")"
    if [ -z "${agent_id}" ]; then
        agent_id="${ADAM_AGENT_ID:-inconnu}"
    fi

    logger "INFO" "[restart_agent] Event #${event_id} — tentative de redémarrage de l'agent '${agent_id}'"

    # Tentative : pkill
    if pkill -x "${agent_id}" 2>/dev/null; then
        logger "INFO" "[restart_agent] Event #${event_id} — agent '${agent_id}' tué"
        sleep 2
        return 0
    fi

    # Si pas trouvé, vérifier s'il y a un PID file
    if [ -f "${PID_DIR}/${agent_id}.pid" ]; then
        local pid
        pid="$(cat "${PID_DIR}/${agent_id}.pid" 2>/dev/null || true)"
        if [ -n "${pid}" ] && kill -0 "${pid}" 2>/dev/null; then
            kill -15 "${pid}" 2>/dev/null || true
            sleep 2
            logger "INFO" "[restart_agent] Event #${event_id} — PID ${pid} tué pour '${agent_id}'"
            return 0
        fi
    fi

    logger "WARN" "[restart_agent] Event #${event_id} — agent '${agent_id}' pas trouvé (déjà arrêté ?)"
    return 0
}

# handle_shell : exécute une commande shell depuis le payload
handle_shell() {
    local event_id="${ADAM_EVENT_ID:-(inconnu)}"
    local commande
    commande="$(extraire_payload "command")"

    if [ -z "${commande}" ]; then
        logger "ERROR" "[shell] Event #${event_id} — aucune commande dans le payload"
        return 1
    fi

    logger "INFO" "[shell] Event #${event_id} — exécution: ${commande}"
    local output
    output="$(eval "${commande}" 2>&1 || true)"
    local exit_code=$?

    logger "INFO" "[shell] Event #${event_id} — exit=${exit_code}, output: $(echo "${output}" | head -5 | tr '\n' ' ')"

    return "${exit_code}"
}

# handle_gpu_oom : libère la VRAM GPU
handle_gpu_oom() {
    local event_id="${ADAM_EVENT_ID:-(inconnu)}"

    logger "INFO" "[gpu_oom] Event #${event_id} — tentative de libération GPU"

    # Lister les processus GPU les plus gourmands
    if ! command -v nvidia-smi &>/dev/null; then
        logger "WARN" "[gpu_oom] nvidia-smi non disponible"
        return 1
    fi

    local procs
    procs="$(nvidia-smi --query-compute-apps=pid,used_memory \
             --format=csv,noheader 2>/dev/null || true)"

    if [ -z "${procs}" ]; then
        logger "INFO" "[gpu_oom] Event #${event_id} — aucun processus GPU"
        return 0
    fi

    # Extraire le PID le plus gourmand
    local max_mem=0
    local max_pid=""

    while IFS=',' read -r pid mem_raw; do
        pid="$(echo "${pid}" | xargs)"
        local mem
        mem="$(echo "${mem_raw}" | xargs | sed 's/ MiB//')"
        if [ "${mem}" -gt "${max_mem}" ] 2>/dev/null; then
            max_mem="${mem}"
            max_pid="${pid}"
        fi
    done <<< "${procs}"

    if [ -n "${max_pid}" ] && [ "${max_pid}" -gt 0 ] 2>/dev/null; then
        logger "INFO" "[gpu_oom] Event #${event_id} — PID ${max_pid} utilise ${max_mem} MiB → SIGTERM"
        kill -15 "${max_pid}" 2>/dev/null || true
        sleep 3

        # Vérifier si toujours vivant
        if kill -0 "${max_pid}" 2>/dev/null; then
            logger "WARN" "[gpu_oom] PID ${max_pid} toujours vivant → SIGKILL"
            kill -9 "${max_pid}" 2>/dev/null || true
        fi

        logger "INFO" "[gpu_oom] Event #${event_id} — PID ${max_pid} libéré"
        return 0
    fi

    logger "INFO" "[gpu_oom] Event #${event_id} — aucun processus à tuer"
    return 0
}

# handle_free_memory : libère la mémoire système
handle_free_memory() {
    local event_id="${ADAM_EVENT_ID:-(inconnu)}"

    logger "INFO" "[free_memory] Event #${event_id} — libération mémoire"

    # Sync puis drop caches
    sync 2>/dev/null || true
    if [ -w /proc/sys/vm/drop_caches ]; then
        echo 3 > /proc/sys/vm/drop_caches 2>/dev/null && \
            logger "INFO" "[free_memory] Cache vidé" || \
            logger "WARN" "[free_memory] Permission refusée pour drop_caches"
    else
        logger "WARN" "[free_memory] /proc/sys/vm/drop_caches non accessible"
    fi

    return 0
}

# handle_clean_disk : nettoie les caches temporaires
handle_clean_disk() {
    local event_id="${ADAM_EVENT_ID:-(inconnu)}"

    logger "INFO" "[clean_disk] Event #${event_id} — nettoyage disque"

    local cibles=(
        "/tmp"
        "/var/tmp"
        "${ADAM_V2_DIR}/logs"
    )

    for cible in "${cibles[@]}"; do
        if [ -d "${cible}" ]; then
            logger "INFO" "[clean_disk] Nettoyage de ${cible}"
            # Nettoyage des fichiers de plus de 7 jours dans /tmp et /var/tmp
            if [ "${cible}" = "/tmp" ] || [ "${cible}" = "/var/tmp" ]; then
                find "${cible}" -type f -atime +7 -delete 2>/dev/null || true
            fi
            # Nettoyage des logs de plus de 30 jours
            if [ "${cible}" = "${ADAM_V2_DIR}/logs" ]; then
                find "${cible}" -name "*.log.*" -mtime +30 -delete 2>/dev/null || true
            fi
        fi
    done

    logger "INFO" "[clean_disk] Nettoyage terminé"
    return 0
}

# ─── Dispatch principal ─────────────────────────────────────────────────────

main() {
    # Valider les entrées
    if ! valide_payload; then
        exit 127
    fi

    local channel="${ADAM_EVENT_CHANNEL:-}"
    local event_id="${ADAM_EVENT_ID:-0}"
    local error_type
    error_type="$(extraire_payload "error_type")"

    logger "INFO" "=== Début event #${event_id} ==="
    logger "INFO" "Canal: ${channel} | Source: ${ADAM_EVENT_SOURCE:-?} | Priorité: ${ADAM_EVENT_PRIORITY:-0}"
    logger "INFO" "Agent: ${ADAM_AGENT_ID:-?} | Type d'erreur: ${error_type:-?}"

    # Déterminer le handler à utiliser
    local handler=""
    local exit_code=0

    case "${channel}" in
        "adam:error")
            case "${error_type}" in
                "service_down"|"service_crash"|"daemon_stopped")
                    handler="restart_service"
                    handle_restart_service || exit_code=$?
                    ;;
                "agent_crash"|"agent_unresponsive")
                    handler="restart_agent"
                    handle_restart_agent || exit_code=$?
                    ;;
                "handler_failed")
                    handler="retry"
                    handle_retry || exit_code=$?
                    ;;
                "zombie_process")
                    # Le handler shell peut exécuter la commande de kill zombie
                    handler="shell"
                    handle_shell || exit_code=$?
                    ;;
                "out_of_memory")
                    handler="free_memory"
                    handle_free_memory || exit_code=$?
                    ;;
                "disk_full")
                    handler="clean_disk"
                    handle_clean_disk || exit_code=$?
                    ;;
                *)
                    logger "WARN" "Type d'erreur non reconnu: ${error_type:-aucun}"
                    handler="unknown"
                    exit_code=2
                    ;;
            esac
            ;;
        "hardware:gpu_alert")
            handler="gpu_oom"
            handle_gpu_oom || exit_code=$?
            ;;
        *)
            logger "WARN" "Canal non géré: ${channel}"
            handler="unknown"
            exit_code=2
            ;;
    esac

    logger "INFO" "Handler: ${handler} | Code: ${exit_code}"

    if [ "${exit_code}" -eq 0 ]; then
        logger "INFO" "=== Fin event #${event_id} — SUCCÈS ==="
    else
        logger "WARN" "=== Fin event #${event_id} — ÉCHEC (code=${exit_code}) ==="
    fi

    return "${exit_code}"
}

# ─── Lancement ──────────────────────────────────────────────────────────────

main "$@"
exit $?
