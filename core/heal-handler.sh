#!/bin/bash
# ────────────────────────────────────────────────────────────
# EVA ADAM v2 — Handler de guérison (Levier 2)
# ────────────────────────────────────────────────────────────
# Ce script est appelé par event_daemon.py quand un événement
# arrive sur le canal 'adam:error'. Il délègue au moteur
# self_heal.py pour diagnostiquer et guérir le problème.
#
# Variables d'environnement passées par le daemon :
#   ADAM_EVENT_ID       — ID de l'événement
#   ADAM_EVENT_CHANNEL  — Canal (adam:error)
#   ADAM_EVENT_SOURCE   — Source de l'événement
#   ADAM_EVENT_PAYLOAD  — Payload JSON
#   ADAM_EVENT_PRIORITY — Priorité (1-5)
#   ADAM_AGENT_ID       — ID de l'agent assigné
#   ADAM_V2_DIR         — Répertoire base d'ADAM v2
# ────────────────────────────────────────────────────────────

set -euo pipefail

ADAM_V2_DIR="${ADAM_V2_DIR:-/home/aza/eva-adam-v2}"
PAYLOAD="${ADAM_EVENT_PAYLOAD:-{\}}"

echo "[heal-handler] Event #${ADAM_EVENT_ID} sur ${ADAM_EVENT_CHANNEL}"
echo "[heal-handler] Payload: ${PAYLOAD}"

# Lancer un scan one-shot du self-healer (--once = un cycle puis arrêt)
cd "${ADAM_V2_DIR}"
python3 self_heal.py --once 2>&1 || {
    echo "[heal-handler] ERREUR: échec du scan self_heal.py"
    exit 1
}

echo "[heal-handler] Scan terminé avec succès"
exit 0
