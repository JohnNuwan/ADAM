#!/usr/bin/env bash
# trigger_doctor.sh — Publie un event "service:unhealthy" sur l'event bus
#                    pour déclencher le docteur périodiquement.
# Usage:  ./trigger_doctor.sh
# Dépend: python3, ~/eva-adam-v2/publish.py, ~/eva-adam-v2/event_bus.py

set -euo pipefail

ADAM_V2_DIR="${ADAM_V2_DIR:-/home/aza/eva-adam-v2}"
PAYLOAD='{"service":"adam-doctor","reason":"periodic_trigger","checked_by":"cron","timestamp":"'"$(date -u +%Y-%m-%dT%H:%M:%SZ)"'"}'

cd "$ADAM_V2_DIR"
python3 publish.py "service:unhealthy" "$PAYLOAD" --source "cron"