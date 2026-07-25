#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════════
# BLUE TEAM — Patch Rapide (exécution sans sudo pour les permissions locales)
# ═══════════════════════════════════════════════════════════════════════════════

set -euo pipefail

echo "═══ BLUE TEAM PATCH — Permissions EVA ═══"

# 1. Logs → 640
find /home/aza/.hermes/logs -type f -name "*.log" -exec chmod 640 {} \; 2>/dev/null
find /home/aza/.hermes/logs -type d -exec chmod 750 {} \; 2>/dev/null
echo "✓ Logs → 640 / 750"

# 2. .env → 600
chmod 600 /home/aza/.hermes/.env 2>/dev/null
echo "✓ .env → 600"

# 3. Config → 600
chmod 600 /home/aza/.hermes/hermes-agent/configs/config.yaml 2>/dev/null
echo "✓ config.yaml → 600"

# 4. .hermes home → 700
chmod 700 /home/aza/.hermes/ 2>/dev/null
echo "✓ ~/.hermes/ → 700"

# 5. Cron → 600
chmod 600 /home/aza/.hermes/cron/jobs.json 2>/dev/null && echo "✓ cron/jobs.json → 600"

# 6. Memoire → 600
find /home/aza/.hermes/memories -type f -exec chmod 600 {} \; 2>/dev/null
find /home/aza/.hermes/memories -type d -exec chmod 700 {} \; 2>/dev/null
echo "✓ Memories → 600/700"

# 7. Dashboard auth log → 640
chmod 640 /home/aza/.hermes/logs/dashboard-auth.log 2>/dev/null || true

echo "═══ Permissions appliquées ═══"

# Vérification finale
echo
echo "Vérification :"
for f in /home/aza/.hermes/logs/*.log; do
    p=$(stat -c "%a" "$f" 2>/dev/null)
    echo "  $p $f"
done
stat -c "%a %n" /home/aza/.hermes/.env
stat -c "%a %n" /home/aza/.hermes/cron/jobs.json