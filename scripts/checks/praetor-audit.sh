#!/usr/bin/env bash
TARGET="."
while [[ $# -gt 0 ]]; do
    case "$1" in
        --path) TARGET="$2"; shift 2 ;;
        *) shift ;;
    esac
done

set -eo pipefail
ERRORS=0
WARNS=0

cd "$TARGET" 2>/dev/null || { echo "Erreur: dossier $TARGET introuvable"; exit 2; }

echo "[PRAETOR] Audit de securite en cours..."

echo "[PRAETOR] Verification fichiers sensibles trackes..."
for sf in .git-credentials .env .env.local .env.prod credentials.json key.pem; do
    git ls-files "$sf" 2>/dev/null | while read -r f; do
        echo "  [ERR] Fichier sensible tracke: $f"
        ERRORS=$((ERRORS+1))
    done
done

echo "[PRAETOR] Recherche de secrets (tokens, clefs)..."
SECRETS_PAT="ghp_[0-9a-zA-Z]\\|gho_[0-9a-zA-Z]\\|github_pat_[0-9a-zA-Z]\\|sk-[A-Za-z0-9]\\|AKIA[0-9A-Z]\\|BEGIN RSA PRIVATE KEY\\|BEGIN OPENSSH PRIVATE KEY\\|password=[^c]"
matches=$(grep -rn -E "$SECRETS_PAT" --include='*.py' --include='*.sh' --include='*.yaml' --include='*.json' \
    --exclude-dir=.git --exclude-dir=venv --exclude-dir=.venv --exclude-dir=__pycache__ --exclude-dir=data \
    --exclude-dir=osint_env --exclude-dir=evolution --exclude-dir=scripts/checks \
    --exclude='*.log' --exclude='*.db' 2>/dev/null | head -20)
if [ -n "$matches" ]; then
    echo "  [ERR] Secret(s) possible(s) detecte(s):"
    echo "$matches" | grep -v 'SECRETS_PAT\|osint_env/lib\|\.venv/lib\|venv/lib' | sed 's/^/    /'
    ERRORS=$((ERRORS+1))
fiecho "[PRAETOR] Verification IP privees..."
ips=$(grep -rnE '(192\.168\.|10\.|172\.1[6-9]\.|172\.2[0-9]\.|172\.3[0-1])'     --include='*.py' --include='*.sh' --include='*.yaml' --include='*.json'     --exclude-dir=.git --exclude-dir=venv --exclude-dir=.venv 2>/dev/null | head -10)
if [ -n "$ips" ]; then
    echo "  [WARN] IP privee(s) dans les fichiers:"
    echo "$ips" | sed 's/^/    /'
    WARNS=$((WARNS+1))
fi

echo "[PRAETOR] Verification bases .db trackees..."
for db in $(git ls-files '*.db' '*.sqlite' '*.sqlite3' 2>/dev/null | head -10); do
    echo "  [WARN] Base de donnees trackee: $db"
    WARNS=$((WARNS+1))
done

if [ $ERRORS -gt 0 ]; then
    echo "[PRAETOR] ALERTE: $ERRORS secret(s) detecte(s), $WARNS avertissement(s)"
    exit 2
elif [ $WARNS -gt 0 ]; then
    echo "[PRAETOR] AVERTISSEMENTS: $WARNS"
    exit 1
else
    echo "[PRAETOR] OK - Aucun secret detecte"
    exit 0
fi
