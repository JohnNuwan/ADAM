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

echo "[SENTINEL] Verification des dependances..."

if [ -f requirements.txt ]; then
    echo "[SENTINEL] requirements.txt present"
else
    if [ -f pyproject.toml ] || [ -f setup.py ] || [ -f setup.cfg ] || [ -f Pipfile ]; then
    echo "[SENTINEL] Fichier de deps present (pyproject.toml|setup.py|Pipfile)"
else
    echo "[SENTINEL] [WARN] Pas de requirements.txt ni de fichier de dependances"
    WARNS=$((WARNS+1))
fi
    WARNS=$((WARNS+1))
fi

for rf in requirements.txt pyproject.toml; do
    if [ -f "$rf" ]; then
        unpinned=$(grep -E "(\"[a-z]|^[a-z])" "$rf" 2>/dev/null | grep -v '>=' | grep -v '==' | grep -v '^#' | grep -v '^$' | grep -v 'name =' | grep -v 'version =' | grep -v 'description' | grep -v 'requires-python' | grep -v 'requires =' | grep -v 'build-backend' | grep -v 'dependencies' | head -10)
        if [ -n "$unpinned" ]; then
            echo "  [WARN] Dep. non pinees dans $rf:"
            echo "$unpinned" | sed 's/^/    /'
            WARNS=$((WARNS+1))
        fi
    fi
done

if [ $WARNS -gt 0 ]; then
    echo "[SENTINEL] AVERTISSEMENTS: $WARNS"
    exit 1
else
    echo "[SENTINEL] OK"
    exit 0
fi
