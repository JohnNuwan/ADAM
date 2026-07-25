#!/bin/bash
# adam-praetor — Handler for config:changed and cron:missed events
# Environment: ADAM_EVENT_CHANNEL, ADAM_EVENT_PAYLOAD, ADAM_EVENT_SOURCE
# Always exits 0. 30s timeout per invocation.
set -o pipefail
CHANNEL="${ADAM_EVENT_CHANNEL:-unknown}"
PAYLOAD="${ADAM_EVENT_PAYLOAD:-}"
if [ -z "$PAYLOAD" ]; then PAYLOAD='{}'; fi
LOGFILE="/home/aza/eva-adam-v2/logs/praetor-handler.log"
ADAM_V2_DIR="/home/aza/eva-adam-v2"

mkdir -p "$(dirname "$LOGFILE")"

log() {
    local level="${1:-INFO}"
    shift
    echo "[$(date -Iseconds)] [${level}] ${CHANNEL}: $*" >> "$LOGFILE"
}

# Parse field from JSON payload (via stdin, handles trailing garbage)
get_payload_field() {
    local field="$1"
    printf '%s\n' "$PAYLOAD" | python3 -c "
import sys, json
s = sys.stdin.read().strip()
# Handle trailing garbage (some events emit }} instead of })
while s and s[-1] != '}':
    s = s[:-1]
# Try parsing, stripping trailing } if needed
for _ in range(3):
    if not s:
        break
    try:
        d = json.loads(s)
        print(d.get('${field}', ''))
        break
    except json.JSONDecodeError:
        s = s[:-1]
" 2>/dev/null
}

validate_python() {
    local filepath="$1"
    if [ ! -f "$filepath" ]; then
        log WARN "File not found, skipping syntax check: ${filepath}"
        return 0
    fi
    log INFO "Validating Python syntax: ${filepath}"
    if timeout 10 python3 -m py_compile "$filepath" 2>>"$LOGFILE"; then
        log OK "Python syntax OK: ${filepath}"
    else
        log ERROR "Python syntax error in ${filepath}"
    fi
}

validate_json() {
    local filepath="$1"
    if [ ! -f "$filepath" ]; then
        log WARN "File not found, skipping validation: ${filepath}"
        return 0
    fi
    log INFO "Validating JSON: ${filepath}"
    if timeout 10 python3 -c "
import json, sys
try:
    with open('${filepath}') as f:
        json.load(f)
    sys.exit(0)
except Exception as e:
    print(f'JSON validation failed: {e}', file=sys.stderr)
    sys.exit(1)
" 2>>"$LOGFILE"; then
        log OK "JSON valid: ${filepath}"
    else
        log ERROR "JSON invalid in ${filepath}"
    fi
}

validate_yaml() {
    local filepath="$1"
    if [ ! -f "$filepath" ]; then
        log WARN "File not found, skipping validation: ${filepath}"
        return 0
    fi
    log INFO "Validating YAML: ${filepath}"
    if timeout 10 python3 -c "
import sys
try:
    import yaml
    with open('${filepath}') as f:
        yaml.safe_load(f)
    sys.exit(0)
except Exception as e:
    print(f'YAML validation failed: {e}', file=sys.stderr)
    sys.exit(1)
" 2>>"$LOGFILE"; then
        log OK "YAML valid: ${filepath}"
    else
        log ERROR "YAML invalid in ${filepath}"
    fi
}

# === Main handler ===
exec 2>>"$LOGFILE"

case "$CHANNEL" in
    config:changed)
        FILEPATH=$(get_payload_field "path")
        EXTENSION=$(get_payload_field "extension")

        if [ -z "$FILEPATH" ]; then
            log WARN "config:changed payload missing 'path' field"
            exit 0
        fi

        # Derive extension from filename if not provided in payload
        if [ -z "$EXTENSION" ]; then
            EXTENSION="${FILEPATH##*.}"
        fi

        # Strip leading dot from extension if present
        EXTENSION="${EXTENSION#.}"

        log INFO "config:changed — ${FILEPATH} (${EXTENSION})"

        # Only validate files under ADAM_V2_DIR
        case "$FILEPATH" in
            "$ADAM_V2_DIR"*)
                case "${EXTENSION,,}" in
                    py)
                        validate_python "$FILEPATH"
                        ;;
                    json)
                        validate_json "$FILEPATH"
                        ;;
                    yaml|yml)
                        validate_yaml "$FILEPATH"
                        ;;
                    *)
                        log INFO "Skipping validation for extension .${EXTENSION}"
                        ;;
                esac
                ;;
            *)
                log INFO "Skipping validation (outside ADAM_V2_DIR): ${FILEPATH}"
                ;;
        esac
        ;;

    cron:missed)
        CRON_NAME=$(get_payload_field "cron")
        [ -z "$CRON_NAME" ] && CRON_NAME=$(get_payload_field "name")
        [ -z "$CRON_NAME" ] && CRON_NAME="unknown"

        log WARN "cron:missed — ${CRON_NAME}"

        # Suggest action based on cron name
        case "$CRON_NAME" in
            *watcher*|*watch*)
                log INFO "suggested action: restart file watcher — check ${ADAM_V2_DIR}/logs/watcher.log"
                ;;
            *heal*|*health*)
                log INFO "suggested action: check daemon health — run 'hermes cron status' or check ${ADAM_V2_DIR}/logs/heal-handler.log"
                ;;
            *critic*)
                log INFO "suggested action: check critic logs at ${ADAM_V2_DIR}/logs/critic-handler.log"
                ;;
            *cicd*|*ci*)
                log INFO "suggested action: check CI/CD pipeline logs at ${ADAM_V2_DIR}/logs/cicd-handler.log"
                ;;
            *)
                log INFO "suggested action: investigate ${CRON_NAME} — check ${ADAM_V2_DIR}/logs/ for relevant logs"
                ;;
        esac
        ;;

    *)
        log INFO "Unhandled channel: ${CHANNEL}"
        ;;
esac

exit 0