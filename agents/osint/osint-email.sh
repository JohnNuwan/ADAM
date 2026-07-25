#!/usr/bin/env bash
# =============================================================================
# ADAM-OSINT — Test OSINT sur cible email
# Utilise le conteneur Kali pour lancer les outils OSINT
# =============================================================================
# Usage: bash ~/scripts/osint-email.sh <email>
# Exemple: bash ~/scripts/osint-email.sh john.nuwan.moncel@gmail.com
# =============================================================================

set -euo pipefail

EMAIL="${1:-john.nuwan.moncel@gmail.com}"
REPORT_DIR="$HOME/.osint/reports/$(date +%Y-%m-%d_%H%M%S)"
mkdir -p "$REPORT_DIR"

echo "══════════════════════════════════════════════════════════════"
echo "  ADAM-OSINT — Test OSINT sur $EMAIL"
echo "  Rapport: $REPORT_DIR"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo "══════════════════════════════════════════════════════════════"

# Vérifier que le conteneur Kali tourne
if ! docker ps --format '{{.Names}}' | grep -q kali-pentest; then
    echo "❌ Conteneur kali-pentest pas démarré"
    exit 1
fi

KALI="docker exec kali-pentest"
USERNAME=$(echo "$EMAIL" | cut -d@ -f1)
DOMAIN=$(echo "$EMAIL" | cut -d@ -f2)

echo ""
echo "┌─── Cible ───┐"
echo "│ Email: $EMAIL"
echo "│ User:  $USERNAME"
echo "│ Domain: $DOMAIN"
echo "└──────────────┘"

# ─── 1. theHarvester — collecte d'infos publiques ────────────────
echo ""
echo "▸ [1/7] theHarvester — collecte d'infos sur $DOMAIN..."
$KALI bash -c "theHarvester -d $DOMAIN -b all -f /shared/report-theharvester.html 2>/dev/null || theharvester -d $DOMAIN -b all -f /shared/report-theharvester.html 2>/dev/null" || echo "  ⚠️ theHarvester non disponible ou erreur"

# ─── 2. holehe — vérification inscriptions sur plateformes ───────
echo ""
echo "▸ [2/7] holehe — vérification des inscriptions sur plateformes..."
$KALI bash -c "holehe $EMAIL > /shared/report-holehe.txt 2>&1" || echo "  ⚠️ holehe non disponible"

# ─── 3. h8mail — recherche dans fuites de données ────────────────
echo ""
echo "▸ [3/7] h8mail — recherche dans fuites de données..."
$KALI bash -c "h8mail -t $EMAIL -o /shared/report-h8mail.json 2>/dev/null" || echo "  ⚠️ h8mail non disponible"

# ─── 4. sherlock — recherche de pseudos sur réseaux sociaux ──────
echo ""
echo "▸ [4/7] sherlock — recherche du pseudo '$USERNAME' sur les réseaux..."
$KALI bash -c "sherlock $USERNAME --timeout 10 --output /shared/report-sherlock.txt 2>/dev/null || sherlock $USERNAME --timeout 10 --print-found 2>/dev/null > /shared/report-sherlock.txt" || echo "  ⚠️ sherlock non disponible"

# ─── 5. recon-ng — reconnaissance approfondie ────────────────────
echo ""
echo "▸ [5/7] recon-ng — reconnaissance approfondie..."
$KALI bash -c "recon-ng -r \"modules search\" 2>/dev/null > /shared/report-recon.txt" || echo "  ⚠️ recon-ng non disponible"

# ─── 6. DNS / WHOIS sur le domaine ───────────────────────────────
echo ""
echo "▸ [6/7] DNS et WHOIS sur $DOMAIN..."
$KALI bash -c "dig $DOMAIN ANY +short > /shared/report-dns.txt 2>&1" || true
$KALI bash -c "whois $DOMAIN > /shared/report-whois.txt 2>&1" || true
$KALI bash -c "host -t MX $DOMAIN >> /shared/report-dns.txt 2>&1" || true
$KALI bash -c "host -t TXT $DOMAIN >> /shared/report-dns.txt 2>&1" || true

# ─── 7. Subfinder / amass — sous-domaines ────────────────────────
echo ""
echo "▸ [7/7] Sous-domaines de $DOMAIN..."
$KALI bash -c "subfinder -d $DOMAIN -silent -o /shared/report-subdomains.txt 2>/dev/null" || echo "  ⚠️ subfinder non disponible"

# ─── Copier les rapports ─────────────────────────────────────────
echo ""
echo "▸ Copie des rapports vers $REPORT_DIR..."
docker cp kali-pentest:/shared/. "$REPORT_DIR/" 2>/dev/null || true

# Nettoyer le dossier shared
$KALI bash -c "rm -f /shared/report-*" 2>/dev/null || true

# ─── Résumé ──────────────────────────────────────────────────────
echo ""
echo "══════════════════════════════════════════════════════════════"
echo "  RAPPORT OSINT — $EMAIL"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo "══════════════════════════════════════════════════════════════"
echo ""
echo "Rapports générés :"
ls -la "$REPORT_DIR/" 2>/dev/null | grep report- || echo "  (aucun rapport)"
echo ""
echo "Dossier : $REPORT_DIR"

# Générer un résumé Markdown
cat > "$REPORT_DIR/summary.md" << SUMMARY
# Rapport OSINT — $EMAIL

**Date :** $(date '+%Y-%m-%d %H:%M:%S')
**Cible :** $EMAIL
**Username :** $USERNAME
**Domaine :** $DOMAIN

## Outils utilisés

1. theHarvester — collecte d'infos publiques
2. holehe — vérification inscriptions plateformes
3. h8mail — fuites de données
4. sherlock — réseaux sociaux
5. recon-ng — reconnaissance
6. DNS/WHOIS — infos domaine
7. subfinder — sous-domaines

## Résultats

Voir les fichiers report-* dans ce dossier pour les détails.
SUMMARY

echo ""
echo "Résumé : $REPORT_DIR/summary.md"
