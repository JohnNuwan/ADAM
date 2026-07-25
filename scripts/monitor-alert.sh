#!/bin/bash
# =============================================================================
# ADAM Monitor Alert Handler
# =============================================================================
# Channels: hardware:disk_alert | hardware:gpu_alert | hardware:ram_alert
#           service:down | service:unhealthy
# Env vars: ADAM_EVENT_CHANNEL, ADAM_EVENT_PAYLOAD (JSON), ADAM_EVENT_SOURCE
# Always exits 0. Logs to ~/eva-adam-v2/logs/monitor-handler.log
# Timeout guard: 30s built-in via timeout wrapper
# =============================================================================

set -euo pipefail

# --- Configuration -----------------------------------------------------------
readonly LOGFILE="${ADAM_V2_DIR:-/home/aza/eva-adam-v2}/logs/monitor-handler.log"
readonly TIMEOUT=28  # slightly under 30s for safety margin

# --- Logging helper ----------------------------------------------------------
log() {
    local level="${1:-INFO}"
    shift
    local timestamp
    timestamp="$(date -Iseconds)"
    echo "[${timestamp}] [${level}] $*" >> "$LOGFILE"
}

log_raw() {
    local timestamp
    timestamp="$(date -Iseconds)"
    echo "[${timestamp}] [RAW] $*" >> "$LOGFILE"
}

ensure_logdir() {
    mkdir -p "$(dirname "$LOGFILE")"
}

# --- Channel handlers --------------------------------------------------------

handle_disk_alert() {
    log "INFO" "=== DISK ALERT ==="

    # 1. Check root filesystem usage
    local pct
    pct="$(df / --output=pcent 2>/dev/null | tail -1 | tr -d ' %')"
    if [[ -z "$pct" ]]; then
        log "WARN" "disk_alert: df returned empty — cannot determine usage %"
        return 0
    fi

    log "INFO" "disk_alert: root filesystem usage ${pct}%"

    # 2. If > 90%, find large files (>100MB) in key directories
    if (( pct > 90 )); then
        log "WARN" "disk_alert: usage is ${pct}% ( > 90% threshold )"

        local search_dirs=("/home/aza" "/home/aza/eva-adam-v2")
        for d in "${search_dirs[@]}"; do
            if [[ -d "$d" ]]; then
                log "INFO" "disk_alert: large files (>100MB) in ${d}:"
                # Run find with a 5s timeout to avoid hanging on large trees
                timeout 5 find "$d" -xdev -type f -size +100M -exec ls -lh {} \; 2>/dev/null | \
                    awk '{print $5, $NF}' | while read -r size path; do
                        log "INFO" "  ${size}  ${path}"
                    done
            fi
        done

        # 3. If > 95%, clean old logs (>7 days) from logs/ directory
        if (( pct > 95 )); then
            log "WARN" "disk_alert: usage is ${pct}% ( > 95% threshold ) — cleaning old logs"
            local log_dir="${ADAM_V2_DIR:-/home/aza/eva-adam-v2}/logs"
            if [[ -d "$log_dir" ]]; then
                local old_count
                old_count="$(find "$log_dir" -name '*.log' -type f -mtime +7 2>/dev/null | wc -l)"
                if (( old_count > 0 )); then
                    find "$log_dir" -name '*.log' -type f -mtime +7 -exec rm -v {} \; 2>/dev/null | \
                        while read -r removed; do
                            log "INFO" "disk_alert: cleaned ${removed}"
                        done
                    log "INFO" "disk_alert: removed ${old_count} old log file(s)"
                else
                    log "INFO" "disk_alert: no log files older than 7 days to clean"
                fi
            fi
        fi
    else
        log "INFO" "disk_alert: usage ${pct}% is under 90% threshold — no action"
    fi
}

handle_gpu_alert() {
    log "INFO" "=== GPU ALERT ==="

    # Check if nvidia-smi is available
    if ! command -v nvidia-smi &>/dev/null; then
        log "WARN" "gpu_alert: nvidia-smi not found — cannot check GPU"
        return 0
    fi

    # Query GPU status — temperature and memory usage
    local gpu_info
    gpu_info="$(timeout 10 nvidia-smi --query-gpu=index,name,temperature.gpu,memory.used,memory.total --format=csv,noheader,nounits 2>/dev/null || true)"

    if [[ -z "$gpu_info" ]]; then
        log "WARN" "gpu_alert: nvidia-smi returned no GPU data"
        return 0
    fi

    log "INFO" "gpu_alert: GPU status:"
    local gpu_alerted=0
    local gpu_free=1  # assume free until proven occupied

    while IFS=',' read -r idx name temp mem_used mem_total; do
        # Trim whitespace
        idx="$(echo "$idx" | xargs)"
        name="$(echo "$name" | xargs)"
        temp="$(echo "$temp" | xargs)"
        mem_used="$(echo "$mem_used" | xargs)"
        mem_total="$(echo "$mem_total" | xargs)"

        # Skip if parsing failed
        [[ -z "$idx" ]] && continue

        local mem_pct=0
        if [[ -n "$mem_total" && "$mem_total" -gt 0 ]]; then
            mem_pct=$(( mem_used * 100 / mem_total ))
        fi

        log "INFO" "  GPU ${idx} (${name}): temp=${temp}°C, mem=${mem_used}/${mem_total}MiB (${mem_pct}%)"

        local this_gpu_alerted=0

        # Check temperature > 90°C
        if [[ -n "$temp" && "$temp" -gt 90 ]]; then
            log "WARN" "gpu_alert: GPU ${idx} temperature ${temp}°C exceeds 90°C threshold"
            this_gpu_alerted=1
        fi

        # Check VRAM > 95%
        if (( mem_pct > 95 )); then
            log "WARN" "gpu_alert: GPU ${idx} VRAM usage ${mem_pct}% exceeds 95% threshold"
            this_gpu_alerted=1
        fi

        # If GPU 0 is in alert and vLLM is running, log warning
        if [[ "$idx" == "0" && "$this_gpu_alerted" -eq 1 ]]; then
            if pgrep -f "vllm" &>/dev/null; then
                log "WARN" "gpu_alert: GPU 0 en alerte et vLLM tourne — vérifier le service vllm"
            fi
        fi

        # Track if ANY GPU is in alert
        if (( this_gpu_alerted )); then
            gpu_alerted=1
        fi

        # Track occupancy — if memory used > 100MiB, GPU is considered occupied
        if [[ -n "$mem_used" && "$mem_used" -gt 100 ]]; then
            gpu_free=0
        fi
    done <<< "$gpu_info"

    # If GPU is free, suggest liberation
    if (( gpu_free && ! gpu_alerted )); then
        log "INFO" "gpu_alert: GPU appears free — suggérer libération mémoire GPU"
    fi

    if (( gpu_alerted == 0 )); then
        log "INFO" "gpu_alert: all GPUs within thresholds"
    fi
}

handle_ram_alert() {
    log "INFO" "=== RAM ALERT ==="

    # 1. Check swap usage
    local swap_total swap_used swap_pct
    swap_total=$(free -m | awk '/Swap:/{print $2}')
    swap_used=$(free -m | awk '/Swap:/{print $3}')

    if [[ -z "$swap_total" || "$swap_total" -eq 0 ]]; then
        log "INFO" "ram_alert: no swap configured"
        swap_pct=0
    else
        swap_pct=$(( swap_used * 100 / swap_total ))
        log "INFO" "ram_alert: swap usage ${swap_used}MiB / ${swap_total}MiB (${swap_pct}%)"
    fi

    # Also log RAM info
    local ram_info
    ram_info="$(free -h | grep -E '^(Mem:|Swap:)' || true)"
    log "INFO" "ram_alert: memory status:"
    while IFS= read -r line; do
        [[ -n "$line" ]] && log "INFO" "  ${line}"
    done <<< "$ram_info"

    # 2. If swap > 80%, identify top 5 processes by RSS
    if (( swap_pct > 80 )); then
        log "WARN" "ram_alert: swap usage ${swap_pct}% exceeds 80% threshold"

        log "INFO" "ram_alert: top 5 processes by RSS (resident memory):"
        local top_procs
        top_procs="$(ps aux --sort=-%rss 2>/dev/null | head -6 || ps aux --sort=-rss 2>/dev/null | head -6)"
        echo "$top_procs" | while read -r line; do
            log "INFO" "  ${line}"
        done
    else
        log "INFO" "ram_alert: swap usage ${swap_pct}% under 80% threshold"
    fi
}

# Map known service names to their systemd unit
known_services() {
    local svc="$1"
    case "$svc" in
        vllm|vllm-*)
            echo "vllm"
            ;;
        ollama|ollama-*)
            echo "ollama"
            ;;
        docker|containerd)
            echo "$svc"
            ;;
        nginx|apache2|httpd)
            echo "$svc"
            ;;
        postgresql*|mysql*|mariadb*|redis*)
            echo "$svc"
            ;;
        ssh|sshd)
            echo "ssh"
            ;;
        *)
            echo ""
            ;;
    esac
}

handle_service_down() {
    local service_name
    service_name="$(echo "${PAYLOAD:-}" | python3 -c "import sys,json; print(json.load(sys.stdin).get('service','unknown-service'))" 2>/dev/null || echo "unknown-service")"

    log "INFO" "=== SERVICE DOWN: ${service_name} ==="

    # Check with systemctl
    if ! command -v systemctl &>/dev/null; then
        log "WARN" "service_down: systemctl not available"
        return 0
    fi

    local status_output
    status_output="$(timeout 5 systemctl status "${service_name}" 2>&1 || true)"
    log "INFO" "service_down: systemctl status ${service_name}:"
    echo "${status_output}" | head -20 | while read -r line; do
        log "INFO" "  ${line}"
    done

    # Suggest restart for known services
    local known
    known="$(known_services "${service_name}")"
    if [[ -n "$known" ]]; then
        log "WARN" "service_down: ${service_name} is a known service (${known}) — suggérer restart"
        # Check if unit exists at all
        if systemctl list-units --all --type=service 2>/dev/null | grep -q "${service_name}"; then
            log "INFO" "service_down: unit found — 'systemctl restart ${service_name}' recommended"
        else
            log "WARN" "service_down: unit ${service_name} not found in systemd"
        fi
    else
        log "INFO" "service_down: ${service_name} is not a known managed service"
    fi
}

handle_service_unhealthy() {
    local service_name
    service_name="$(echo "${PAYLOAD:-}" | python3 -c "import sys,json; print(json.load(sys.stdin).get('service','unknown-service'))" 2>/dev/null || echo "unknown-service")"

    log "INFO" "=== SERVICE UNHEALTHY: ${service_name} ==="

    if ! command -v systemctl &>/dev/null; then
        log "WARN" "service_unhealthy: systemctl not available"
        return 0
    fi

    local status_output
    status_output="$(timeout 5 systemctl status "${service_name}" 2>&1 || true)"
    log "INFO" "service_unhealthy: systemctl status ${service_name}:"
    echo "${status_output}" | head -20 | while read -r line; do
        log "INFO" "  ${line}"
    done

    local known
    known="$(known_services "${service_name}")"
    if [[ -n "$known" ]]; then
        log "INFO" "service_unhealthy: ${service_name} reconnu — monitoring only, pas de restart automatique"
    fi
}

# =============================================================================
# MAIN — dispatch by channel
# =============================================================================

# Read environment
CHANNEL="${ADAM_EVENT_CHANNEL:-unknown}"
PAYLOAD="${ADAM_EVENT_PAYLOAD:-}"
SOURCE="${ADAM_EVENT_SOURCE:-unknown}"

# Ensure log directory exists
ensure_logdir

# Log the incoming event
log "INFO" "=== MONITOR HANDLER START ==="
log "INFO" "channel=${CHANNEL} source=${SOURCE} payload=${PAYLOAD}"

# Dispatch with a global timeout (30s per the spec)
case "${CHANNEL}" in
    hardware:disk_alert)
        timeout "${TIMEOUT}" bash -c "$(declare -f log); $(declare -f log_raw); $(declare -f handle_disk_alert); ADAM_V2_DIR='${ADAM_V2_DIR:-/home/aza/eva-adam-v2}'; LOGFILE='${LOGFILE}'; PAYLOAD='${PAYLOAD}'; handle_disk_alert" 2>&1 || log "WARN" "disk_alert handler timed out or failed"
        ;;
    hardware:gpu_alert)
        timeout "${TIMEOUT}" bash -c "$(declare -f log); $(declare -f log_raw); $(declare -f handle_gpu_alert); LOGFILE='${LOGFILE}'; handle_gpu_alert" 2>&1 || log "WARN" "gpu_alert handler timed out or failed"
        ;;
    hardware:ram_alert)
        timeout "${TIMEOUT}" bash -c "$(declare -f log); $(declare -f log_raw); $(declare -f handle_ram_alert); LOGFILE='${LOGFILE}'; handle_ram_alert" 2>&1 || log "WARN" "ram_alert handler timed out or failed"
        ;;
    service:down)
        timeout "${TIMEOUT}" bash -c "$(declare -f log); $(declare -f log_raw); $(declare -f known_services); $(declare -f handle_service_down); ADAM_V2_DIR='${ADAM_V2_DIR:-/home/aza/eva-adam-v2}'; LOGFILE='${LOGFILE}'; PAYLOAD='${PAYLOAD}'; handle_service_down" 2>&1 || log "WARN" "service:down handler timed out or failed"
        ;;
    service:unhealthy)
        timeout "${TIMEOUT}" bash -c "$(declare -f log); $(declare -f log_raw); $(declare -f known_services); $(declare -f handle_service_unhealthy); ADAM_V2_DIR='${ADAM_V2_DIR:-/home/aza/eva-adam-v2}'; LOGFILE='${LOGFILE}'; PAYLOAD='${PAYLOAD}'; handle_service_unhealthy" 2>&1 || log "WARN" "service:unhealthy handler timed out or failed"
        ;;
    monitor:alert)
        # Alerte d'agent stale envoyée par adam-doctor
        agent_type="$(echo "${PAYLOAD:-}" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('type','unknown'))" 2>/dev/null || echo 'unknown')"
        stale_agents="$(echo "${PAYLOAD:-}" | python3 -c "import sys,json; d=json.load(sys.stdin); print(', '.join(d.get('agents',[])))" 2>/dev/null || echo 'unknown')"
        log "WARN" "agent_stale: ${stale_agents} (type=${agent_type})"
        log "INFO" "monitor:alert reçu de adam-doctor — agents sans heartbeat récent"
        ;;
    *)
        log "WARN" "unknown channel: ${CHANNEL}"
        ;;
esac

log "INFO" "=== MONITOR HANDLER END ==="

# ──────────────────────────────────────────────
# Follow-up events — chaînes entre agents
# ──────────────────────────────────────────────
PUBLISH="${ADAM_V2_DIR:-/home/aza/eva-adam-v2}/publish.py"

case "${CHANNEL}" in
    hardware:ram_alert)
        # RAM alert → déclencher adam-doctor via service:unhealthy
        python3 "$PUBLISH" service:unhealthy "{\"service\":\"system\",\"reason\":\"ram_alert\",\"source_agent\":\"adam-monitor\"}" --source adam-monitor 2>/dev/null
        log "INFO" "→ published service:unhealthy for adam-doctor"
        ;;
    hardware:disk_alert)
        # Disk alert → déclencher adam-doctor
        python3 "$PUBLISH" service:unhealthy "{\"service\":\"filesystem\",\"reason\":\"disk_alert\",\"source_agent\":\"adam-monitor\"}" --source adam-monitor 2>/dev/null
        log "INFO" "→ published service:unhealthy for adam-doctor"
        ;;
    hardware:gpu_alert)
        # GPU alert → déclencher adam-praetor via config:changed
        python3 "$PUBLISH" config:changed "{\"component\":\"gpu\",\"type\":\"alert\",\"source_agent\":\"adam-monitor\"}" --source adam-monitor 2>/dev/null
        log "INFO" "→ published config:changed for adam-praetor"
        ;;
    service:down)
        # Service down → déclencher adam-doctor via service:restarted (pour qu'il vérifie)
        python3 "$PUBLISH" service:restarted "{\"service\":\"${service_name:-unknown}\",\"action\":\"investigate\",\"source_agent\":\"adam-monitor\"}" --source adam-monitor 2>/dev/null
        log "INFO" "→ published service:restarted for adam-doctor"
        ;;
esac

# Always exit cleanly
exit 0
