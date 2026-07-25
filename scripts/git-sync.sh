#!/usr/bin/env bash
# =============================================================================
# git-sync.sh — Synchronisation automatique ADAM (git pull + push)
# =============================================================================
# Usage : ./scripts/git-sync.sh [message]
#   - Sans argument : commit auto + pull + push
#   - Avec argument  : utilise le message fourni
# =============================================================================

set -euo pipefail

REPO_DIR="$HOME/eva-adam-v2"
REMOTE_NAME="origin"
BRANCH="main"
COMMIT_MSG="${1:-}"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

info()  { echo -e "${CYAN}[ADAM-GIT]${NC} $1"; }
ok()    { echo -e "${GREEN}[✓]${NC} $1"; }
warn()  { echo -e "${YELLOW}[!]${NC} $1"; }
err()   { echo -e "${RED}[✗]${NC} $1"; }

cd "$REPO_DIR"
info "Dépôt : $(basename $(git rev-parse --show-toplevel))"
info "Branche : $(git branch --show-current)"
info "Remote : $(git remote get-url $REMOTE_NAME 2>/dev/null || echo 'aucune')"

# ---- 1. Vérification remote SSH ----
REMOTE_URL=$(git remote get-url "$REMOTE_NAME" 2>/dev/null || true)
if [[ -z "$REMOTE_URL" ]]; then
    err "Aucun remote configuré"
    exit 1
fi

# ---- 2. Auth SSH GitHub ----
SSH_TEST=$(ssh -o StrictHostKeyChecking=accept-new -T git@github.com 2>&1) || true
if ! echo "$SSH_TEST" | grep -q "successfully authenticated"; then
    err "Authentification SSH GitHub échouée"
    exit 1
fi
ok "Authentification SSH GitHub validée"

# ---- 3. PULL avant tout (récupère les modifs distantes) ----
info "Pull depuis origin/$BRANCH..."
git pull --rebase "$REMOTE_NAME" "$BRANCH" 2>&1 || {
    warn "Pull échoué — tentative de merge..."
    git pull "$REMOTE_NAME" "$BRANCH" 2>&1 || {
        err "Pull échoué — conflits détectés !"
        err "Résous manuellement, puis relance"
        exit 1
    }
}
ok "Pull effectué — dépôt à jour"

# ---- 4. Vérifier changements à commit ----
if git diff --quiet HEAD && git diff --cached --quiet && [ -z "$(git ls-files --others --exclude-standard)" ]; then
    info "Aucun changement à commit — dépôt propre"
    info "Rien à push"
    exit 0
fi

# ---- 5. Message de commit ----
if [ -z "$COMMIT_MSG" ]; then
    N_MOD=$(git diff --name-only HEAD 2>/dev/null | wc -l)
    N_NEW=$(git ls-files --others --exclude-standard | wc -l)
    N_DEL=$(git diff --diff-filter=D --name-only HEAD 2>/dev/null | wc -l)
    TIMESTAMP=$(date '+%Y-%m-%d %H:%M')
    COMMIT_MSG="[ADAM] Sync auto — $TIMESTAMP"
    CHANGES=""
    [ "$N_MOD" -gt 0 ] && CHANGES="${CHANGES}${N_MOD} modifié(s), "
    [ "$N_NEW" -gt 0 ] && CHANGES="${CHANGES}${N_NEW} nouvel(s), "
    [ "$N_DEL" -gt 0 ] && CHANGES="${CHANGES}${N_DEL} supprimé(s)"
    CHANGES="${CHANGES%, }"
    [ -n "$CHANGES" ] && COMMIT_MSG="$COMMIT_MSG — $CHANGES"
fi

# ---- 6. Add, Commit ----
info "Ajout des fichiers..."
git add -A
ok "Fichiers stagés"
info "Commit : $COMMIT_MSG"
git commit -m "$COMMIT_MSG" || { warn "Commit vide"; exit 1; }
ok "Commit effectué"

# ---- 7. Push ----
info "Push vers origin/$BRANCH..."
git push "$REMOTE_NAME" "$BRANCH" 2>&1 || {
    err "Push échoué"
    exit 1
}
ok "Push réussi !"

echo ""
echo -e "${GREEN}══════════════════════════════════════════${NC}"
echo -e "${GREEN}  Synchronisation terminée avec succès  ${NC}"
echo -e "${GREEN}══════════════════════════════════════════${NC}"
echo "  Dépôt   : $(basename $(git rev-parse --show-toplevel))"
echo "  Remote  : $REMOTE_URL"
echo "  Branche : $BRANCH"
echo "  Commit  : $(git rev-parse --short HEAD)"
echo ""
