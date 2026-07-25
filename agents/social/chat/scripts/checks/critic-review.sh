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

echo "[CRITIC] Verification syntaxe Python..."
TMPFILE=$(mktemp)
python3 -m py_compile ./core/self_heal.py 2>$TMPFILE && rc=0 || rc=$?
if [ $rc -ne 0 ]; then
    echo "  [ERR] Erreur syntaxe: core/self_heal.py"
    cat $TMPFILE | head -3 | sed 's/^/    /'
    ERRORS=$((ERRORS+1))
fi
rm -f $TMPFILE

echo "[CRITIC] Recherche TODO/FIXME/HACK..."
for pattern in TODO FIXME HACK XXX; do
    matches=$(grep -rn "$pattern" --include='*.py' --include='*.sh' --include='*.yaml'         --exclude-dir=.git --exclude-dir=venv --exclude-dir=.venv --exclude-dir=__pycache__         --exclude-dir=osint_env --exclude-dir=evolution 2>/dev/null | head -20)
    if [ -n "$matches" ]; then
        echo "  [WARN] $pattern trouve:"
        echo "$matches" | sed 's/^/    /'
        WARNS=$((WARNS+1))
    fi
done

echo "[CRITIC] Verification print() dans core/..."
if [ -d core ]; then
    prints=$(grep -rn '^ *print(' core --include='*.py' 2>/dev/null | grep -v '__pycache__' | head -10)
    if [ -n "$prints" ]; then
        echo "  [WARN] print() dans core/:"
        echo "$prints" | sed 's/^/    /'
        WARNS=$((WARNS+1))
    fi
fi

if [ $ERRORS -gt 0 ]; then
    echo "[CRITIC] ECHEC: $ERRORS erreur(s), $WARNS avertissement(s)"
    exit 2
elif [ $WARNS -gt 0 ]; then
    echo "[CRITIC] AVERTISSEMENT: $WARNS avertissement(s)"
    exit 1
else
    echo "[CRITIC] OK"
    exit 0
fi
