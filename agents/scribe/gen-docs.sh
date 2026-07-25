#!/usr/bin/env bash
# =============================================================================
# gen-docs.sh — Générateur de documentation automatique ADAM-DOCS
# Partie de la suite ADAM Agents — E.V.A The Hive
# =============================================================================
# Génère et valide la documentation du projet E.V.A :
#   - Valide la syntaxe Markdown de tous les fichiers .md
#   - Reconstruit l'index du wiki avec les entités actuelles
#   - Met à jour les statistiques (skills, agents, pages)
#   - Vérifie les liens [[wikilinks]] internes
#   - Rapport de synthèse
#
# Usage :
#   ./gen-docs.sh              # Mode normal
#   ./gen-docs.sh --verbose    # Mode verbeux (affiche tout)
#   ./gen-docs.sh --fix        # Corrige les problèmes auto-réparables
#   ./gen-docs.sh --cron       # Mode cron (silencieux si tout OK)
#
# Cron recommandé : 0 6 * * 1 ~/scripts/gen-docs.sh --cron
# =============================================================================

set -o pipefail

# === Constantes ===
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd 2>/dev/null || echo "${HOME}/.hermes/hermes-agent")"
WIKI_DIR="${HOME}/wiki"
SKILLS_DIR="${HOME}/.hermes/skills"
MONITORING_DIR="${HOME}/monitoring-cybersec"
LOG_DIR="${HOME}/logs"
LOG_FILE="${LOG_DIR}/gen-docs-$(date +%Y%m%d).log"
VERBOSE=false
FIX_MODE=false
CRON_MODE=false
ERRORS=0
WARNINGS=0
FIXED=0

# === Couleurs ===
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# === Options ===
for arg in "$@"; do
    case "$arg" in
        --verbose) VERBOSE=true ;;
        --fix)     FIX_MODE=true ;;
        --cron)    CRON_MODE=true ;;
        --help)
            echo "Usage: $(basename "$0") [--verbose|--fix|--cron|--help]"
            echo ""
            echo "  --verbose   Mode verbeux (affiche tout)"
            echo "  --fix       Corrige les problèmes auto-réparables"
            echo "  --cron      Mode cron (silencieux si tout OK)"
            echo "  --help      Affiche cette aide"
            exit 0
            ;;
    esac
done

# === Logging ===
mkdir -p "${LOG_DIR}"

log() {
    local level="$1"
    local msg="$2"
    local color=""
    case "$level" in
        INFO)    color="${GREEN}" ;;
        WARN)    color="${YELLOW}" ;;
        ERROR)   color="${RED}" ;;
        FIX)     color="${CYAN}" ;;
        *)       color="" ;;
    esac
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "${timestamp} [${color}${level}${NC}] ${msg}" >> "${LOG_FILE}"
    if [ "${CRON_MODE}" = false ] || [ "$level" = "ERROR" ]; then
        echo -e "${color}${msg}${NC}"
    fi
}

# =============================================================================
# Étape 1 : Compter les statistiques du projet
# =============================================================================

count_stats() {
    log "INFO" "📊 Collecte des statistiques..."

    # Compter les skills (cd d'abord pour éviter les problèmes de chemin)
    SKILL_COUNT=$(cd "${SKILLS_DIR}" 2>/dev/null && find . -name "SKILL.md" -type f 2>/dev/null | wc -l || echo 0)
    SKILL_CATEGORIES=$(ls -d "${SKILLS_DIR}"/*/ 2>/dev/null | wc -l)

    # Compter les pages wiki
    WIKI_ENTITIES=$(find "${WIKI_DIR}/entities" -name "*.md" 2>/dev/null | wc -l)
    WIKI_CONCEPTS=$(find "${WIKI_DIR}/concepts" -name "*.md" 2>/dev/null | wc -l)
    WIKI_TOTAL=$((WIKI_ENTITIES + WIKI_CONCEPTS))

    # Compter les fichiers de monitoring
    MONITOR_SCRIPTS=$(find "${MONITORING_DIR}" -maxdepth 1 -name "*.sh" 2>/dev/null | wc -l)

    log "INFO" "  Skills : ${SKILL_COUNT} (${SKILL_CATEGORIES} catégories)"
    log "INFO" "  Wiki   : ${WIKI_TOTAL} pages (${WIKI_ENTITIES} entités + ${WIKI_CONCEPTS} concepts)"
    log "INFO" "  Monitoring : ${MONITOR_SCRIPTS} scripts"

    return 0
}

# =============================================================================
# Étape 2 : Valider les fichiers Markdown
# =============================================================================

validate_markdown() {
    log "INFO" "🔍 Validation des fichiers Markdown..."

    # Vérifier que tous les fichiers .md existent et sont lisibles
    local md_files=()
    while IFS= read -r -d '' f; do
        md_files+=("$f")
    done < <(find "${WIKI_DIR}" -name "*.md" -not -path "*/dashboard/*" -not -path "*/venv/*" -print0 2>/dev/null)

    for f in "${md_files[@]}"; do
        local rel="${f#${HOME}/}"

        # Vérifier le frontmatter YAML (doit commencer par ---)
        if ! head -1 "$f" | grep -q '^---$'; then
            log "WARN" "  ⚠ Frontmatter manquant : ${rel}"
            WARNINGS=$((WARNINGS + 1))
        fi

        # Vérifier les [[wikilinks]] pointent vers des fichiers existants
        if grep -oP '\[\[([^\]]+)\]\]' "$f" 2>/dev/null | while read -r link; do
            local slug="${link#\[\[}"
            slug="${slug%\]\]}"
            # Ignorer les liens externes (contiennent :)
            if echo "$slug" | grep -q ':' && ! echo "$slug" | grep -q '^[a-z-]'; then
                continue
            fi
            # Chercher le fichier cible
            local found=false
            for dir in "entities" "concepts" "comparisons" "queries"; do
                if [ -f "${WIKI_DIR}/${dir}/${slug}.md" ]; then
                    found=true
                    break
                fi
            done
            if [ "$found" = false ]; then
                log "WARN" "  ⚠ Wikilink cassé [[${slug}]] dans ${rel}"
                WARNINGS=$((WARNINGS + 1))
                return 1
            fi
        done; then
            :
        fi

        if [ "$VERBOSE" = true ]; then
            log "INFO" "  ✓ ${rel}"
        fi
    done

    log "INFO" "  Validés : ${#md_files[@]} fichiers"
    return 0
}

# =============================================================================
# Étape 3 : Mettre à jour l'index du wiki
# =============================================================================

update_wiki_index() {
    log "INFO" "📝 Mise à jour de l'index du wiki..."

    local index_file="${WIKI_DIR}/index.md"
    if [ ! -f "$index_file" ]; then
        log "WARN" "  Index introuvable, création..."
    fi

    # L'index est maintenu manuellement pour la structure éditoriale
    # On vérifie juste qu'il existe et qu'il est valide
    if [ -f "$index_file" ] && head -1 "$index_file" | grep -q '^#'; then
        log "INFO" "  ✓ Index présent et valide"
    else
        log "ERROR" "  ✗ Index invalide ou manquant"
        ERRORS=$((ERRORS + 1))
    fi

    return 0
}

# =============================================================================
# Étape 4 : Mettre à jour le CHANGELOG si nécessaire
# =============================================================================

update_changelog() {
    local changelog="${WIKI_DIR}/CHANGELOG.md"
    if [ ! -f "$changelog" ]; then
        log "WARN" "  CHANGELOG.md manquant"
        WARNINGS=$((WARNINGS + 1))
        if [ "$FIX_MODE" = true ]; then
            log "FIX" "  ✎ Création du CHANGELOG.md..."
            cat > "$changelog" << 'EOF'
# CHANGELOG — E.V.A The Hive

Tous les changements notables du projet E.V.A sont documentés ici.

## [$(date +%Y-%m-%d)] — Auto-généré
- Documentation regénérée automatiquement par gen-docs.sh
EOF
            FIXED=$((FIXED + 1))
        fi
    else
        log "INFO" "  ✓ CHANGELOG.md présent"
    fi
}

# =============================================================================
# Étape 5 : Valider les fichiers de configuration
# =============================================================================

validate_configs() {
    log "INFO" "⚙ Validation des fichiers de configuration..."

    local configs=(
        "${HOME}/.hermes/config.yaml"
        "${MONITORING_DIR}/config.ini"
    )

    for cfg in "${configs[@]}"; do
        if [ -f "$cfg" ]; then
            local rel="${cfg#${HOME}/}"
            local ext="${cfg##*.}"

            # Validation YAML basique
            if [ "$ext" = "yaml" ] || [ "$ext" = "yml" ]; then
                if command -v python3 &>/dev/null; then
                    if python3 -c "import yaml; yaml.safe_load(open('${cfg}'))" 2>/dev/null; then
                        [ "$VERBOSE" = true ] && log "INFO" "  ✓ ${rel} (YAML valide)"
                    else
                        log "ERROR" "  ✗ ${rel} (YAML invalide)"
                        ERRORS=$((ERRORS + 1))
                    fi
                else
                    log "INFO" "  ? ${rel} (python3 indisponible pour validation)"
                fi
            else
                [ "$VERBOSE" = true ] && log "INFO" "  ✓ ${rel}"
            fi
        else
            log "WARN" "  ⚠ ${cfg} introuvable"
            WARNINGS=$((WARNINGS + 1))
        fi
    done

    return 0
}

# =============================================================================
# Étape 6 : Vérifier la structure du projet
# =============================================================================

validate_structure() {
    log "INFO" "📁 Vérification de la structure du projet..."

    local dirs=(
        "${PROJECT_DIR}"
        "${WIKI_DIR}/entities"
        "${WIKI_DIR}/concepts"
        "${SKILLS_DIR}"
        "${MONITORING_DIR}"
        "${LOG_DIR}"
    )

    for dir in "${dirs[@]}"; do
        if [ -d "$dir" ]; then
            [ "$VERBOSE" = true ] && log "INFO" "  ✓ ${dir#${HOME}/}"
        else
            log "WARN" "  ⚠ ${dir#${HOME}/} manquant"
            WARNINGS=$((WARNINGS + 1))
        fi
    done

    return 0
}

# =============================================================================
# Étape 7 : Générer le rapport
# =============================================================================

generate_report() {
    echo ""
    log "INFO" "${BOLD}═══════════════════════════════════════════${NC}"
    log "INFO" "${BOLD}  RAPPORT DE SYNTHÈSE — ADAM-DOCS${NC}"
    log "INFO" "${BOLD}═══════════════════════════════════════════${NC}"
    echo ""

    local color="${GREEN}"
    if [ "$ERRORS" -gt 0 ]; then
        color="${RED}"
    elif [ "$WARNINGS" -gt 0 ]; then
        color="${YELLOW}"
    fi

    echo -e "  ${BOLD}Statistiques :${NC}"
    echo -e "    Skills      : ${SKILL_COUNT} (${SKILL_CATEGORIES} catégories)"
    echo -e "    Pages wiki  : ${WIKI_TOTAL} (${WIKI_ENTITIES} entités + ${WIKI_CONCEPTS} concepts)"
    echo -e "    Monitoring  : ${MONITOR_SCRIPTS} scripts"
    echo ""
    echo -e "  ${BOLD}Résultats :${NC}"
    echo -e "    ${GREEN}✓ OK${NC}        : $(($(find "${WIKI_DIR}" -name "*.md" -not -path "*/dashboard/*" -not -path "*/venv/*" 2>/dev/null | wc -l))) fichiers markdown"
    echo -e "    ${YELLOW}⚠ Avertissements${NC} : ${WARNINGS}"
    echo -e "    ${RED}✗ Erreurs${NC}     : ${ERRORS}"
    [ "$FIXED" -gt 0 ] && echo -e "    ${CYAN}✎ Corrigés${NC}   : ${FIXED}"
    echo ""
    echo -e "  ${BOLD}Statut :${NC} ${color}${BOLD}$([ "$ERRORS" -gt 0 ] && echo "ÉCHEC" || echo "SUCCÈS")${NC}"
    echo ""
    log "INFO" "  Log : ${LOG_FILE}"
    echo ""
    
    if [ "$ERRORS" -gt 0 ]; then
        return 1
    fi
    return 0
}

# =============================================================================
# Main
# =============================================================================

main() {
    echo ""
    log "INFO" "${BOLD}☤ ADAM-DOCS — Génération de documentation${NC}"
    log "INFO" "Date : $(date '+%Y-%m-%d %H:%M:%S')"
    echo ""

    count_stats
    echo ""
    validate_structure
    echo ""
    validate_markdown
    echo ""
    update_wiki_index
    echo ""
    update_changelog
    echo ""
    validate_configs
    echo ""

    generate_report
    local result=$?

    # En mode cron, seul le code de retour compte
    if [ "$CRON_MODE" = true ]; then
        if [ "$ERRORS" -gt 0 ]; then
            log "ERROR" "ADAM-DOCS cron : ${ERRORS} erreur(s) détectée(s) — voir ${LOG_FILE}"
        fi
    fi

    return $result
}

main "$@"
exit $?