#!/bin/bash
# adam-backup — Handler sauvegarde (backup:failed retry)
# Usage: backup.sh [--retry]
# Env vars: ADAM_EVENT_CHANNEL, ADAM_EVENT_PAYLOAD, ADAM_EVENT_SOURCE
# Retry backup of critical files to ~/backups/adam-v2/ with rotation 5 max.
# Always exits 0.

set -euo pipefail

ADAM_V2_DIR="${ADAM_V2_DIR:-/home/aza/eva-adam-v2}"
LOGFILE="${ADAM_V2_DIR}/logs/backup-handler.log"
BACKUP_ROOT="/home/aza/backups/adam-v2"
TIMESTAMP="$(date -Iseconds)"

mkdir -p "$(dirname "$LOGFILE")"
mkdir -p "$BACKUP_ROOT"

log() {
    local level="${1:-INFO}"
    local msg="${2:-}"
    echo "[${TIMESTAMP}] [${level}] ${msg}" >> "$LOGFILE"
}

# --- Parse args ---
MODE="event"
if [ "${1:-}" = "--retry" ]; then
    MODE="retry"
    shift
fi

# Log event context
CHANNEL="${ADAM_EVENT_CHANNEL:-unknown}"
PAYLOAD="${ADAM_EVENT_PAYLOAD:-}"
if [ -z "$PAYLOAD" ]; then PAYLOAD='{}'; fi
SOURCE="${ADAM_EVENT_SOURCE:-unknown}"

log "INFO" "backup-handler invoked: mode=${MODE} channel=${CHANNEL} source=${SOURCE}"

# If this is a backup:failed event, log the failure details
if [ "${CHANNEL}" = "backup:failed" ]; then
    log "WARN" "Backup failure reported — payload: ${PAYLOAD}"
fi

# --- Collect source paths (glob expands in caller via unquoted pattern) ---
BACKUP_NAME="backup-${TIMESTAMP}"
BACKUP_DIR="${BACKUP_ROOT}/${BACKUP_NAME}"

SOURCES=()
collect_sources() {
    for item; do
        if [ -e "$item" ]; then
            SOURCES+=("$item")
        fi
    done
}

collect_sources "${ADAM_V2_DIR}/event_bus.db"
collect_sources "${ADAM_V2_DIR}"/*.py
collect_sources "/home/aza/jepa_eva/checkpoints_jepa"
collect_sources "/home/aza/jepa_eva/registry_arena_validated/champions"

if [ "${#SOURCES[@]}" -eq 0 ]; then
    log "WARN" "No source files to backup (all paths missing)"
    exit 0
fi

# --- Perform backup ---
mkdir -p "$BACKUP_DIR"
total_size=0
backed_up_count=0

for src in "${SOURCES[@]}"; do
    rel_path="${src#/}"
    dest="${BACKUP_DIR}/${rel_path}"
    mkdir -p "$(dirname "$dest")"

    if [ -d "$src" ]; then
        # Directory: cp -r the contents into dest/
        # Use /dev/null trick to suppress stderr from cp
        if cp -rT -- "$src" "$dest" 2>/dev/null; then
            backed_up_count=$((backed_up_count + 1))
            log "INFO" "Backed up dir: ${src} -> ${dest}"
        else
            log "ERROR" "cp failed for dir: ${src}"
        fi
    else
        # File
        if cp -- "$src" "$dest" 2>/dev/null; then
            backed_up_count=$((backed_up_count + 1))
            log "INFO" "Backed up file: ${src} -> ${dest}"
        else
            log "ERROR" "cp failed for file: ${src}"
        fi
    fi

    local_size=$(du -sb "$src" 2>/dev/null | cut -f1 || echo 0)
    total_size=$((total_size + local_size))
done

if [ "$backed_up_count" -gt 0 ]; then
    human_size=$(numfmt --to=iec "${total_size}" 2>/dev/null || echo "${total_size} bytes")
    log "INFO" "Backup complete: ${BACKUP_DIR} (${backed_up_count} items, ${human_size})"
    echo "Backup: ${backed_up_count} items, ${human_size}"
else
    log "ERROR" "Backup failed: no items were backed up"
    rmdir "$BACKUP_DIR" 2>/dev/null || true
fi

# --- Rotation: keep max 5 backups, remove oldest ---
MAX_BACKUPS=5
backup_count=$(ls -1d "${BACKUP_ROOT}"/backup-* 2>/dev/null | wc -l)
if [ "$backup_count" -gt "$MAX_BACKUPS" ]; then
    excess=$((backup_count - MAX_BACKUPS))
    log "INFO" "Rotation: ${backup_count} backups found, removing ${excess} oldest"
    ls -1d "${BACKUP_ROOT}"/backup-* 2>/dev/null | sort | head -n "$excess" | while read -r old; do
        rm -rf -- "$old"
        log "INFO" "Removed old backup: ${old}"
    done
fi

# --- Final summary ---
final_count=$(ls -1d "${BACKUP_ROOT}"/backup-* 2>/dev/null | wc -l)
log "INFO" "Done. Backup root: ${BACKUP_ROOT} (${final_count} backups retained)"
exit 0