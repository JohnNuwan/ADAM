#!/bin/bash
# setup-backup-dest.sh — À exécuter avec : sudo bash setup-backup-dest.sh
# Crée le répertoire de destination pour ADAM-BACKUP

set -e

echo "=== ADAM-BACKUP — Configuration de la destination ==="
echo ""

DEST="/mnt/data/backups"

if [ -d "$DEST" ]; then
    echo "✓ $DEST existe déjà"
else
    echo "→ Création de $DEST ..."
    mkdir -p "$DEST"
    echo "✓ Créé"
fi

echo "→ Attribution des permissions à aza:aza ..."
chown aza:aza "$DEST"
echo "✓ OK"

echo ""
echo "=== Terminé ==="
ls -la "$(dirname "$DEST")" | grep backups