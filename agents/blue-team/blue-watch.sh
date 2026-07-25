#!/bin/bash
# adam-blue — Handler sécurité (permission_drift, suid_change, vulnerability_detected)
# Réécrit avec vraie logique sécurité. Toujours exit 0.
set -uo pipefail

CHANNEL="${ADAM_EVENT_CHANNEL:-unknown}"
PAYLOAD="${ADAM_EVENT_PAYLOAD:-}"
ADAM_V2_DIR="${ADAM_V2_DIR:-/home/aza/eva-adam-v2}"
[[ -z "$PAYLOAD" ]] && PAYLOAD='{}'
LOGFILE="${ADAM_V2_DIR}/logs/blue-handler.log"
BASELINE_DIR="${HOME}/.config/adam"
SUID_BASELINE="${BASELINE_DIR}/suid-baseline.txt"
FIX_FLAG=false

[[ "$*" == *"--fix"* ]] && FIX_FLAG=true

mkdir -p "$(dirname "$LOGFILE")" "$BASELINE_DIR"

log() {
    local level="$1" msg="$2"
    echo "[$(date -Iseconds)] [${level}] ${msg}" >> "$LOGFILE"
}

# ──────────────────────────────────────────────
# 1. security:permission_drift
# ──────────────────────────────────────────────
handle_permission_drift() {
    # Payload attendu: {"file":"/path","expected":"0644","actual":"0777"}
    local file expected actual
    file="$(echo "$PAYLOAD" | python3 -c "import sys,json; print(json.load(sys.stdin).get('file',''))" 2>/dev/null || true)"
    expected="$(echo "$PAYLOAD" | python3 -c "import sys,json; print(json.load(sys.stdin).get('expected',''))" 2>/dev/null || true)"
    actual="$(echo "$PAYLOAD" | python3 -c "import sys,json; print(json.load(sys.stdin).get('actual',''))" 2>/dev/null || true)"

    if [[ -z "$file" || -z "$expected" || -z "$actual" ]]; then
        log "WARN" "permission_drift: payload incomplet — file='${file}' expected='${expected}' actual='${actual}'"
        return
    fi

    log "INFO" "permission_drift: file=${file} expected=${expected} actual=${actual}"

    if [[ "$FIX_FLAG" == true ]] && [[ -f "$file" ]]; then
        chmod "$expected" "$file" 2>/dev/null && \
            log "FIX" "permission_drift: chmod ${expected} → ${file}" || \
            log "WARN" "permission_drift: echec chmod sur ${file}"
    fi
}

# ──────────────────────────────────────────────
# 2. security:suid_change
# ──────────────────────────────────────────────
handle_suid_change() {
    local current_suid
    current_suid="$(find / -perm -4000 -type f 2>/dev/null | sort)"
    local current_count
    current_count="$(echo "$current_suid" | grep -c . || true)"

    log "INFO" "suid_change: ${current_count} fichiers SUID detectes"

    if [[ -f "$SUID_BASELINE" ]]; then
        local baseline baseline_count
        baseline="$(cat "$SUID_BASELINE")"
        baseline_count="$(echo "$baseline" | grep -c . || true)"

        local added removed
        added="$(comm -13 <(echo "$baseline") <(echo "$current_suid") 2>/dev/null || true)"
        removed="$(comm -23 <(echo "$baseline") <(echo "$current_suid") 2>/dev/null || true)"

        if [[ -n "$added" ]]; then
            log "ALERT" "suid_change: NOUVEAUX fichiers SUID ajoutes:"
            while IFS= read -r f; do
                [[ -n "$f" ]] && log "ALERT" "  + ${f}"
            done <<< "$added"
        fi

        if [[ -n "$removed" ]]; then
            log "INFO" "suid_change: fichiers SUID supprimes:"
            while IFS= read -r f; do
                [[ -n "$f" ]] && log "INFO" "  - ${f}"
            done <<< "$removed"
        fi

        if [[ -z "$added" && -z "$removed" ]]; then
            log "INFO" "suid_change: baseline inchangee (${baseline_count} fichiers)"
        fi
    else
        log "INFO" "suid_change: aucune baseline existante — creation baseline initiale"
    fi

    # Sauvegarder la baseline courante (meme sans --fix, on tracke)
    echo "$current_suid" > "$SUID_BASELINE"
    log "INFO" "suid_change: baseline mise a jour (${current_count} fichiers)"

    if [[ "$FIX_FLAG" == true ]]; then
        if [[ -n "$added" ]]; then
            log "INFO" "suid_change: --fix actif — SUID ajoutes detectes (suppression trop dangereuse, inspection recommandee)"
        fi
    fi
}

# ──────────────────────────────────────────────
# 3. security:vulnerability_detected
# ──────────────────────────────────────────────
handle_vulnerability_detected() {
    local pkg severity cve
    pkg="$(echo "$PAYLOAD" | python3 -c "import sys,json; print(json.load(sys.stdin).get('package',''))" 2>/dev/null || true)"
    severity="$(echo "$PAYLOAD" | python3 -c "import sys,json; print(json.load(sys.stdin).get('severity',''))" 2>/dev/null || true)"
    cve="$(echo "$PAYLOAD" | python3 -c "import sys,json; print(json.load(sys.stdin).get('cve',''))" 2>/dev/null || true)"

    log "ALERT" "vulnerability_detected: package=${pkg} severity=${severity} cve=${cve}"

    if [[ "$FIX_FLAG" == true ]]; then
        log "FIX" "vulnerability_detected: suggestion → apt update && apt upgrade -y"
    fi
}

# ──────────────────────────────────────────────
# Dispatch + follow-up events (chaînes entre agents)
# ──────────────────────────────────────────────
PUBLISH="${ADAM_V2_DIR}/publish.py"

case "$CHANNEL" in
    security:permission_drift)
        handle_permission_drift
        # → Publier security:alert pour adam-sentinel
        python3 "$PUBLISH" security:alert "{\"type\":\"permission_drift\",\"file\":\"${file:-unknown}\",\"severity\":\"low\",\"source_agent\":\"adam-blue\"}" --source adam-blue 2>/dev/null
        log "INFO" "→ published security:alert for adam-sentinel"
        ;;
    security:suid_change)
        handle_suid_change
        # → Publier security:alert pour adam-sentinel si nouveaux SUID
        if [[ -n "${added:-}" ]]; then
            python3 "$PUBLISH" security:alert "{\"type\":\"suid_added\",\"count\":\"$(echo \"$added\" | grep -c . || echo 1)\",\"severity\":\"medium\",\"source_agent\":\"adam-blue\"}" --source adam-blue 2>/dev/null
            log "INFO" "→ published security:alert (suid_added) for adam-sentinel"
        fi
        ;;
    security:vulnerability_detected)
        handle_vulnerability_detected
        # → Publier security:alert pour adam-sentinel
        python3 "$PUBLISH" security:alert "{\"type\":\"vulnerability\",\"package\":\"${pkg:-unknown}\",\"severity\":\"${severity:-medium}\",\"cve\":\"${cve:-}\",\"source_agent\":\"adam-blue\"}" --source adam-blue 2>/dev/null
        log "INFO" "→ published security:alert (vulnerability) for adam-sentinel"
        ;;
    *)
        log "WARN" "canal inconnu: ${CHANNEL}"
        ;;
esac

exit 0