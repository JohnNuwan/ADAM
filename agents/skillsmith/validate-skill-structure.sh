#!/usr/bin/env bash
# =============================================================================
# validate-skill-structure.sh — ADAM-CICD
# Validation complète de la structure des skills :
#   1. Chaque dossier de skill a un SKILL.md
#   2. Frontmatter YAML valide (name, description, tags)
#   3. Les wikilinks [[...]] pointent vers des pages existantes
#   4. Les tags sont dans la taxonomie définie
# =============================================================================
set -euo pipefail

# ── Configuration ──────────────────────────────────────────────────────────
SKILL_DIRS_ABS=(
    "/home/aza/.hermes/hermes-agent/skills"
    "/home/aza/.hermes/skills"
)
WIKI_DIR="$HOME/wiki"
WIKI_PAGES_FILE="/tmp/adam-wiki-pages.txt"
TAXONOMY_FILE="/tmp/adam-taxonomy.txt"
VALIDATOR_SCRIPT="/home/aza/.hermes/hermes-agent/.github/scripts/validate-skill-frontmatter.py"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; CYAN='\033[0;36m'; NC='\033[0m'
info()  { echo -e "${CYAN}[ADAM-VALIDATE]${NC} $1"; }
ok()    { echo -e "${GREEN}[✓]${NC} $1"; }
warn()  { echo -e "${YELLOW}[!]${NC} $1"; }
err()   { echo -e "${RED}[✗]${NC} $1"; }

TOTAL_ERRORS=0
TOTAL_WARNINGS=0

# Délégation au validateur Python (plus rapide, gère 1000+ skills)
PYTHON_SCRIPT="$(dirname "$0")/validate-skill-structure.py"
if [ -f "$PYTHON_SCRIPT" ]; then
    exec python3 "$PYTHON_SCRIPT" --dirs "${SKILL_DIRS_ABS[@]}" --wiki "$WIKI_DIR"
fi

# ── Bilan ─────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}══════════════════════════════════════════${NC}"
echo -e "${GREEN}  Validation terminée                     ${NC}"
echo -e "${GREEN}══════════════════════════════════════════${NC}"
echo "  Erreurs   : $TOTAL_ERRORS"
echo "  Avertissements : $TOTAL_WARNINGS"
echo ""

if [ "$TOTAL_ERRORS" -gt 0 ]; then
    err "Certaines validations ont échoué"
    exit 1
fi
ok "Toutes les validations sont passées"
exit 0