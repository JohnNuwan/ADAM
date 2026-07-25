#!/usr/bin/env bash
# =============================================================================
# auto-pr.sh — ADAM-CICD
# Détecte les nouveaux skills/modifications, crée une branche,
# commit, push et ouvre une Pull Request via gh CLI ou API REST GitHub
# =============================================================================
set -euo pipefail

# ── Configuration ──────────────────────────────────────────────────────────
REPO_DIR="$HOME/.hermes/hermes-agent"
REMOTE="origin"
BRANCH_PREFIX="auto/skills"
DATE_TAG=$(date '+%Y-%m-%d')
BRANCH_NAME="${BRANCH_PREFIX}-${DATE_TAG}"
GH_REPO="JohnNuwan/EVA_CORE"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; CYAN='\033[0;36m'; NC='\033[0m'
info()  { echo -e "${CYAN}[ADAM-PR]${NC} $1"; }
ok()    { echo -e "${GREEN}[✓]${NC} $1"; }
warn()  { echo -e "${YELLOW}[!]${NC} $1"; }
err()   { echo -e "${RED}[✗]${NC} $1"; }

# ── Étape 1 : Se placer dans le dépôt ─────────────────────────────────────
cd "$REPO_DIR"
info "Dépôt : $(basename "$(git rev-parse --show-toplevel)")"

# ── Étape 2 : Détecter les changements ────────────────────────────────────
NEW_SKILLS=$(git ls-files --others --exclude-standard -- 'skills/*/SKILL.md' 2>/dev/null || true)
MODIFIED_SKILLS=$(git diff --name-only HEAD -- 'skills/*/SKILL.md' 2>/dev/null || true)

if [ -z "$NEW_SKILLS" ] && [ -z "$MODIFIED_SKILLS" ]; then
    info "Aucun nouveau skill ou modification détectée"
    exit 0
fi

echo ""
info "Changements détectés :"
if [ -n "$NEW_SKILLS" ]; then
    echo "  ✨ Nouveaux skills :"
    echo "$NEW_SKILLS" | while IFS= read -r s; do echo "    - $(basename "$(dirname "$s")")"; done
fi
if [ -n "$MODIFIED_SKILLS" ]; then
    echo "  🔧 Skills modifiés :"
    echo "$MODIFIED_SKILLS" | while IFS= read -r s; do echo "    - $(basename "$(dirname "$s")")"; done
fi

# ── Étape 3 : Vérifier si gh CLI est disponible ───────────────────────────
USE_GH=false
if command -v gh &>/dev/null; then
    if gh auth status 2>&1 | grep -q "active account"; then
        USE_GH=true
        ok "gh CLI disponible et authentifié"
    else
        warn "gh CLI présent mais non authentifié — utilisation de l'API REST via curl"
    fi
else
    warn "gh CLI non installé — utilisation de l'API REST via curl"
    warn "Installe gh CLI pour une meilleure expérience :"
    warn "  sudo apt-get install gh && gh auth login"
fi

# ── Étape 4 : Synchroniser avec la branche principale ─────────────────────
info "Récupération des dernières modifications..."

# Vérifier si la branche existe déjà
if git show-ref --verify --quiet "refs/heads/$BRANCH_NAME"; then
    warn "La branche $BRANCH_NAME existe déjà — suppression"
    git branch -D "$BRANCH_NAME"
fi

git fetch origin main 2>/dev/null || true
git checkout -b "$BRANCH_NAME" origin/main 2>/dev/null || git checkout -b "$BRANCH_NAME" main

# ── Étape 5 : Ajouter les fichiers et commit ──────────────────────────────
info "Ajout des fichiers..."

# Ajouter les nouveaux skills et les fichiers modifiés
git add skills/ .github/ 2>/dev/null

# Vérifier qu'il y a des changements stagés
if git diff --cached --quiet; then
    info "Aucun fichier à commit après staging"
    git checkout main
    git branch -D "$BRANCH_NAME" 2>/dev/null || true
    exit 0
fi

# Construire le message de commit
N_NEW=$(echo "$NEW_SKILLS" | wc -l)
N_MOD=$(echo "$MODIFIED_SKILLS" | wc -l)

if [ "$N_NEW" -gt 0 ] && [ "$N_MOD" -gt 0 ]; then
    COMMIT_MSG="[AUTO] Nouveaux skills ($N_NEW) + modifications ($N_MOD) — $DATE_TAG"
elif [ "$N_NEW" -gt 0 ]; then
    COMMIT_MSG="[AUTO] Nouveaux skills ($N_NEW) — $DATE_TAG"
else
    COMMIT_MSG="[AUTO] Skills modifiés ($N_MOD) — $DATE_TAG"
fi

info "Message : $COMMIT_MSG"
git commit -m "$COMMIT_MSG" -m "Généré automatiquement par ADAM-CICD

Nouveaux skills :
$(echo "$NEW_SKILLS" | sed 's/^/  - /' || echo '  (aucun)')

Skills modifiés :
$(echo "$MODIFIED_SKILLS" | sed 's/^/  - /' || echo '  (aucun)')"
ok "Commit effectué : $(git rev-parse --short HEAD)"

# ── Étape 6 : Push et créer la PR ─────────────────────────────────────────
info "Push vers $REMOTE/$BRANCH_NAME..."
if ! git push "$REMOTE" "$BRANCH_NAME" 2>&1; then
    err "Push échoué — vérifie l'authentification SSH ou le remote"
    warn "Remote : $(git remote get-url "$REMOTE")"
    git checkout main
    exit 1
fi
ok "Push réussi"

PR_TITLE="[AUTO] Skills : $(echo "$NEW_SKILLS $MODIFIED_SKILLS" | head -c 80)"
PR_BODY="## Résumé des changements

**Date :** $DATE_TAG

### Nouveaux skills
$(echo "$NEW_SKILLS" | while IFS= read -r s; do echo "- ✨ \`$(basename "$(dirname "$s")")\`"; done || echo "- (aucun)")

### Skills modifiés
$(echo "$MODIFIED_SKILLS" | while IFS= read -r s; do echo "- 🔧 \`$(basename "$(dirname "$s")")\`"; done || echo "- (aucun)")

### Validation
- [ ] Tests CI passés
- [ ] Frontmatter YAML valide
- [ ] Tags dans la taxonomie
- [ ] Wikilinks valides

---
_Généré automatiquement par ADAM-CICD_

"

if [ "$USE_GH" = true ]; then
    info "Création de la PR via gh CLI..."
    gh pr create \
        --repo "$GH_REPO" \
        --base main \
        --head "$BRANCH_NAME" \
        --title "$PR_TITLE" \
        --body "$PR_BODY" \
        --label "auto-pr,skills"
    ok "PR créée : $(gh pr view --repo "$GH_REPO" --json url -q .url)"
else
    info "Création de la PR via API REST..."

    # Récupérer le token GitHub
    GH_TOKEN="${GH_TOKEN:-}"
    if [ -f "$HOME/.hermes/.env" ]; then
        source "$HOME/.hermes/.env"
        GH_TOKEN="${GH_TOKEN:-${GITHUB_TOKEN:-}}"
    fi

    if [ -z "$GH_TOKEN" ]; then
        err "Aucun token GitHub trouvé"
        err "Définis GH_TOKEN dans ~/.hermes/.env ou exporte-le"
        warn "La branche $BRANCH_NAME a été poussée — crée la PR manuellement :"
        warn "  https://github.com/$GH_REPO/compare/$BRANCH_NAME?expand=1"
        git checkout main
        exit 1
    fi

    PR_RESPONSE=$(curl -s -X POST "https://api.github.com/repos/$GH_REPO/pulls" \
        -H "Authorization: token $GH_TOKEN" \
        -H "Accept: application/vnd.github.v3+json" \
        -d "$(jq -n \
            --arg title "$PR_TITLE" \
            --arg head "$BRANCH_NAME" \
            --arg base "main" \
            --arg body "$PR_BODY" \
            '{title: $title, head: $head, base: $base, body: $body}')")

    PR_URL=$(echo "$PR_RESPONSE" | jq -r '.html_url // empty')
    if [ -n "$PR_URL" ] && [ "$PR_URL" != "null" ]; then
        ok "PR créée : $PR_URL"
    else
        err "Échec de création de la PR"
        err "Réponse : $(echo "$PR_RESPONSE" | jq -r '.message // .')"
        warn "La branche $BRANCH_NAME a été poussée"
    fi
fi

# ── Retour sur main ──────────────────────────────────────────────────────
git checkout main 2>/dev/null || true

# ── Bilan ─────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}══════════════════════════════════════════${NC}"
echo -e "${GREEN}  Auto-PR terminé                        ${NC}"
echo -e "${GREEN}══════════════════════════════════════════${NC}"
echo "  Branche  : $BRANCH_NAME"
echo "  Commit   : $(git rev-parse --short HEAD 2>/dev/null || echo 'N/A')"
echo "  Date     : $DATE_TAG"
echo ""

exit 0