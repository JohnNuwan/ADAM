#!/bin/bash
# adam-red — Handler OSINT / Red Team
# Canal: osint:alert
# Réagit aux alertes OSINT, scan de surface web, veille sécurité

set +e

# Récupérer le payload (fallback si vide)
PAYLOAD="${ADAM_EVENT_PAYLOAD:-{}}"
CHANNEL="${ADAM_EVENT_CHANNEL:-unknown}"
SOURCE="${ADAM_EVENT_SOURCE:-unknown}"
AGENT_ID="${ADAM_AGENT_ID:-adam-red}"

LOG_DIR="${ADAM_V2_DIR:-$HOME/eva-adam-v2}/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/red-handler.log"

log() {
    echo "[$(date -u +%Y-%m-%dT%H:%M:%S+00:00)] [$AGENT_ID] $1" >> "$LOG_FILE"
}

log "🔔 Canal: $CHANNEL | Source: $SOURCE"

# Parser le payload (essayer jq, sinon python)
MSG=$(echo "$PAYLOAD" | jq -r '.msg // empty' 2>/dev/null) || \
MSG=$(echo "$PAYLOAD" | python3 -c "import sys,json; print(json.loads(sys.stdin.read() or '{}').get('msg',''))" 2>/dev/null) || \
MSG=""

log "📝 Message: $MSG"

# --- Action OSINT ---
# 1. Scanner les ports ouverts locaux (surface d'attaque)
log "🔍 Scan surface d'attaque locale..."
OPEN_PORTS=$(ss -tlnp 2>/dev/null | grep LISTEN | awk '{print $4}' | rev | cut -d: -f1 | rev | sort -u | head -20)
log "📡 Ports en écoute: $(echo $OPEN_PORTS | tr '\n' ' ')"

# 2. Vérifier les connexions établies suspectes
SUSPICIOUS=$(ss -tnp 2>/dev/null | grep ESTAB | awk '{print $5}' | sort -u | head -10)
log "🔗 Connexions établies: $(echo $SUSPICIOUS | tr '\n' ' ')"

# 3. Vérifier les processus récents avec CPU élevé
HIGH_CPU=$(ps aux --sort=-%cpu | head -6 | tail -5)
log "📊 Top CPU: $(echo $HIGH_CPU | tr '\n' ' ')"

# 4. Vérifier les tentatives de connexion failed (auth.log)
FAILED_LOGINS=$(journalctl -u ssh --since "5 min ago" 2>/dev/null | grep -c "Failed password" || echo "0")
log "🚨 Tentatives SSH échouées (5min): $FAILED_LOGINS"

# 5. Vérifier les fichiers modifiés récemment dans /etc
RECENT_ETC=$(find /etc -type f -mmin -30 2>/dev/null | head -10)
if [ -n "$RECENT_ETC" ]; then
    log "⚠️ Fichiers /etc modifiés récemment: $(echo $RECENT_ETC | tr '\n' ' ')"
else
    log "✅ Aucune modification récente dans /etc"
fi

# Rapport
log "✅ Scan OSINT terminé — Ports: $(echo $OPEN_PORTS | wc -w), SSH fails: $FAILED_LOGINS"

exit 0
