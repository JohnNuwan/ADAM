#!/usr/bin/env bash
# =============================================================================
# ADAM-GATE — Portail de vérification pré-commit
# =============================================================================
# Orchestre les 4 vérificateurs avant d'autoriser un commit/push.
# Usage : adam-gate.sh [--path <dir>]
#   --path   : dossier à analyser (défaut: répertoire courant)
#   --strict : échoue aussi sur les avertissements (pas que les erreurs)
# Retour : 0 = gate passé, 1 = avertissements, 2 = gate bloqué
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CHECKS_DIR="$SCRIPT_DIR/checks"
TARGET="${1:-.}"
STRICT=false

# Parse args
while [[ $# -gt 0 ]]; do
    case "$1" in
        --path) TARGET="$2"; shift 2 ;;
        --strict) STRICT=true; shift ;;
        *) shift ;;
    esac
done

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}══════════════════════════════════════════${NC}"
echo -e "${CYAN}  ADAM-GATE — Vérification pré-commit     ${NC}"
echo -e "${CYAN}══════════════════════════════════════════${NC}"
echo "  Cible : $TARGET"
echo ""

# ── Lancer les 4 vérificateurs ──
CHECKS=("critic-review.sh" "praetor-audit.sh" "sentinel-deps.sh" "doctor-health.sh")
RESULTS=()
ALL_PASS=true
ANY_FAIL=false

for check in "${CHECKS[@]}"; do
    check_path="$CHECKS_DIR/$check"
    if [ ! -f "$check_path" ]; then
        echo -e "${RED}[GATE] Vérificateur introuvable: $check${NC}"
        RESULTS+=("FAIL")
        ANY_FAIL=true
        continue
    fi

    echo -e "${CYAN}── Lancement de $check ──${NC}"
    set +e
    output=$($check_path --path "$TARGET" 2>&1)
    rc=$?
    set -e

    echo "$output"
    echo ""

    if [ $rc -eq 0 ]; then
        RESULTS+=("PASS")
    elif [ $rc -eq 1 ]; then
        RESULTS+=("WARN")
        if $STRICT; then
            ANY_FAIL=true
        fi
    else
        RESULTS+=("FAIL")
        ANY_FAIL=true
    fi
done

# ── Bilan final ──
echo -e "${CYAN}══════════════════════════════════════════${NC}"
echo -e "${CYAN}  RÉSULTAT ADAM-GATE                     ${NC}"
echo -e "${CYAN}══════════════════════════════════════════${NC}"

for i in "${!CHECKS[@]}"; do
    check="${CHECKS[$i]}"
    result="${RESULTS[$i]}"
    case "$result" in
        PASS) echo -e "  ${GREEN}[✓]${NC} $check" ;;
        WARN) echo -e "  ${YELLOW}[!]${NC} $check — avertissements" ;;
        FAIL) echo -e "  ${RED}[✗]${NC} $check — ÉCHEC" ;;
    esac
done
echo ""

if $ANY_FAIL; then
    echo -e "${RED}⛔ GATE BLOQUÉ — Corrigez les erreurs avant de committer.${NC}"
    exit 2
elif $STRICT && [ -n "$(echo "${RESULTS[@]}" | grep WARN)" ]; then
    echo -e "${YELLOW}⚠ GATE PASSÉ AVEC AVERTISSEMENTS (mode --strict)${NC}"
    exit 1
else
    echo -e "${GREEN}✅ GATE PASSÉ — Vous pouvez committer.${NC}"
    exit 0
fi

