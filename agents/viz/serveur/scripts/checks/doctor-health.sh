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

echo "[DOCTOR] Diagnostic de sante..."

echo "[DOCTOR] Recherche conflits de merge..."
CONFLICT_FILES=$(find . -name '*.py' -o -name '*.sh' -o -name '*.yaml' -o -name '*.json' -o -name '*.md' 2>/dev/null | grep -v '.git/' | grep -v 'venv/' | grep -v '.venv/' | grep -v 'osint_env/' | grep -v 'wordlists/' | grep -v 'evolution/' | head -100)
if [ -n "$CONFLICT_FILES" ]; then
    conflicts=$(grep -l '<<<<<<< HEAD' $CONFLICT_FILES 2>/dev/null | head -10)
    if [ -n "$conflicts" ]; then
        echo "  [ERR] Conflits de merge dans:"
        echo "$conflicts" | sed 's/^/    /'
        WARNS=$((WARNS+1))
    fi
fi
echo "[DOCTOR] Verification coherence agents.yaml vs agents/..."
if [ -f agents.yaml ]; then
    for dir in agents/*/; do
        aname=$(basename "$dir")
        if ! grep -q "name: $aname" agents.yaml 2>/dev/null; then
            echo "  [WARN] Dossier agents/$aname/ absent de agents.yaml"
            WARNS=$((WARNS+1))
        fi
    done
fi

echo "[DOCTOR] Verification fichiers orphelins .pyc..."
pyc=$(find . -name '*.pyc' -not -path './.git/*' 2>/dev/null | head -10)
if [ -n "$pyc" ]; then
    echo "  [WARN] .pyc orphelins trouves"
    WARNS=$((WARNS+1))
fi

if [ $ERRORS -gt 0 ]; then
    echo "[DOCTOR] ERREURS: $ERRORS, AVERTISSEMENTS: $WARNS"
    exit 2
elif [ $WARNS -gt 0 ]; then
    echo "[DOCTOR] PROBLÈMES: $WARNS"
    exit 1
else
    echo "[DOCTOR] OK"
    exit 0
fi
