#!/usr/bin/env bash
# =============================================================================
# Git pre-commit hook — Appelle ADAM-GATE avant chaque commit
# =============================================================================
# Installation : copier dans .git/hooks/pre-commit
#   cp scripts/pre-commit.sh .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit
# =============================================================================

echo ""
echo "══════════════════════════════════════════"
echo "  ADAM-GATE — Vérification pré-commit"
echo "══════════════════════════════════════════"

REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null)

if [ -f "$REPO_ROOT/scripts/adam-gate.sh" ]; then
    $REPO_ROOT/scripts/adam-gate.sh --path "$REPO_ROOT"
    result=$?
    if [ $result -ne 0 ]; then
        echo ""
        echo "⛔ Commit bloqué par ADAM-GATE (code: $result)"
        echo "   Corrigez les problèmes et réessayez."
        echo "   Pour forcer (déconseillé): git commit --no-verify"
        exit 1
    fi
else
    echo "⚠ adam-gate.sh introuvable — hook désactivé"
fi

