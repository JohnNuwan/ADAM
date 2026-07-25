#!/bin/bash
# healed-handler.sh — Handler pour les events adam:healed
# Log l'event de auto-guérison et confirme réception
# Args: $1 = JSON payload de l'event

PAYLOAD="${1:-{}}"

# Log minimal dans le syslog local
logger -t adam-healed "Heal event received: $PAYLOAD" 2>/dev/null || true

# Exit 0 = succès
exit 0
