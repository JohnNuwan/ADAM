#!/usr/bin/env bash
# ============================================================================
# ADAM-SENTINEL — Mise a jour des skills (sentinel-update.sh)
# ============================================================================
# Apres un scan de veille, verifie si les skills existants sont a jour,
# cree de nouveaux skills pour les sujets emergents, marque les obsoletes.
# Execute apres sentinel-watch.sh
# ============================================================================
set -euo pipefail

SENTINEL_DIR="$HOME/wiki/sentinel"
SKILLS_DIR="$HOME/.hermes/hermes-agent/skills"
TODAY=$(date +%Y-%m-%d)
RAPPORT="$SENTINEL_DIR/daily-$TODAY.md"

# ============================================================================
# CONFIGURATION : mapping domaines -> skills
# ============================================================================
# "domaine|pattern_skill|balise_de_nouveaute"
declare -A DOMAIN_SKILL_MAP
DOMAIN_SKILL_MAP["cybersec"]="cybersecurite,security,penetration,exploit,forensics,hacking"
DOMAIN_SKILL_MAP["ai-ml"]="ia,llm,machine-learning,deep-learning,neural,transformer,AI"
DOMAIN_SKILL_MAP["osint"]="osint,open-source-intelligence"
DOMAIN_SKILL_MAP["devops"]="devops,ci-cd,kubernetes,docker,ansible,terraform"
DOMAIN_SKILL_MAP["cloud"]="cloud,aws,azure,gcp,cloud-computing"
DOMAIN_SKILL_MAP["design"]="design,ui,ux,css,figma,animation,3d"
DOMAIN_SKILL_MAP["blockchain"]="blockchain,smart-contract,solidity,web3"
DOMAIN_SKILL_MAP["crypto"]="crypto,cryptomonnaie,defi,trading"
DOMAIN_SKILL_MAP["network"]="network,reseau,protocole,dns,5g"
DOMAIN_SKILL_MAP["programmation"]="programmation,python,javascript,rust,golang,react,framework"

# ============================================================================
# FONCTIONS
# ============================================================================

log() {
    echo "[$(date +%H:%M:%S)] [UPDATE] $*"
}

# Verifie si un skill existe (recherche par mot-cle dans le nom)
skill_exists() {
    local mot_cle="$1"
    if [ ! -d "$SKILLS_DIR" ]; then
        return 1
    fi
    # Chercher dans les noms de repertoires et les fichiers SKILL.md
    find "$SKILLS_DIR" -maxdepth 2 -name "SKILL.md" 2>/dev/null | while read -r f; do
        if grep -qi "$mot_cle" "$f" 2>/dev/null; then
            return 0
        fi
    done
    return 1
}

# Compte le nombre de skills dans un domaine
count_domain_skills() {
    local pattern="$1"
    local count=0
    if [ ! -d "$SKILLS_DIR" ]; then
        echo 0
        return
    fi
    IFS=',' read -ra PATTERNS <<< "$pattern"
    for p in "${PATTERNS[@]}"; do
        local c
        c=$(find "$SKILLS_DIR" -maxdepth 2 -name "SKILL.md" -exec grep -li "$p" {} \; 2>/dev/null | wc -l)
        count=$((count + c))
    done
    echo "$count"
}

# Extrait les nouveautes d'un domaine depuis le rapport du jour
extract_nouveautes() {
    local domaine="$1"
    if [ ! -f "$RAPPORT" ]; then
        echo ""
        return
    fi
    # Extrait la section entre "### DOMAINE" et "---"
    sed -n "/^### $domaine/,/^---/p" "$RAPPORT" 2>/dev/null | grep "^- " || true
}

# ============================================================================
# EXECUTION PRINCIPALE
# ============================================================================

log "=== ADAM-SENTINEL UPDATE ==="
log "Verification des skills pour $TODAY"

if [ ! -f "$RAPPORT" ]; then
    log "⚠️  Aucun rapport du jour trouve. Execute sentinel-watch.sh d'abord."
    exit 1
fi

echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║        ADAM-SENTINEL — Mise a jour des skills            ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

RAPPORT_ACTIONS=()

for DOMAINE in "${!DOMAIN_SKILL_MAP[@]}"; do
    PATTERN="${DOMAIN_SKILL_MAP[$DOMAINE]}"
    
    log "→ Verification [$DOMAINE]..."
    
    NOUVEAUTES=$(extract_nouveautes "$DOMAINE")
    NB_SKILLS=$(count_domain_skills "$PATTERN")
    
    echo "   Skills existants : $NB_SKILLS"
    
    if [ -z "$NOUVEAUTES" ]; then
        echo "   Aucune nouveaute ce jour."
        RAPPORT_ACTIONS+=("[$DOMAINE] ✅ A jour ($NB_SKILLS skills)")
        continue
    fi
    
    # Extraire le nombre de nouveautes
    NB_NOUVEAUTES=$(echo "$NOUVEAUTES" | wc -l)
    echo "   $NB_NOUVEAUTES nouveaute(s) detectee(s)"
    
    if [ "$NB_NOUVEAUTES" -gt 3 ]; then
        echo "   ⚠️  Beaucoup d'activite sur ce domaine — envisager nouveau skill"
        RAPPORT_ACTIONS+=("[$DOMAINE] 🔥 $NB_NOUVEAUTES nouveautes — nouveau skill a creer")
    else
        RAPPORT_ACTIONS+=("[$DOMAINE] 📝 $NB_NOUVEAUTES nouveaute(s)")
    fi
done

# ============================================================================
# RAPPORT DE SYNTHESE
# ============================================================================

echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║        Bilan de mise a jour des skills                   ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

for ACTION in "${RAPPORT_ACTIONS[@]}"; do
    echo "  $ACTION"
done

echo ""
echo "Rapport : $RAPPORT"

# ============================================================================
# SAUVEGARDER L'ETAT POUR LA PROCHAINE EXECUTION
# ============================================================================

echo "$(date +%s)" > "$SENTINEL_DIR/.last-update"
printf '%s\n' "${RAPPORT_ACTIONS[@]}" > "$SENTINEL_DIR/.last-actions"

log "=== Mise a jour terminee ==="
exit 0