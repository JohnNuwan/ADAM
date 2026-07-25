#!/usr/bin/env bash
# =============================================================================
# ADAM-DOCTOR — Médecin de l'équipe ADAM
# Surveille l'état de tous les ADAMs, diagnostique les pannes,
# tente des réparations automatiques, et signale les échecs.
# =============================================================================
# Usage:
#   ./doctor-watch.sh --once    # Un seul cycle
#   ./doctor-watch.sh --fix     # Un cycle + réparations
#   ./doctor-watch.sh           # Mode boucle (5 min)
# =============================================================================

set +u

LOG_DIR="$HOME/.doctor/logs"
STATE_FILE="$HOME/.doctor/state.json"
INFIRMERY_DIR="$HOME/.doctor/infirmary"
WIKI_FILE="$HOME/wiki/entities/adam-doctor.md"
CRON_FILE="$HOME/.hermes/cron/jobs.json"

mkdir -p "$LOG_DIR" "$INFIRMERY_DIR" "$HOME/.doctor"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; BLUE='\033[0;34m'; NC='\033[0m'

log()      { echo -e "[$(date '+%H:%M:%S')] $*" | tee -a "$LOG_DIR/doctor.log"; }
log_ok()   { echo -e "[$(date '+%H:%M:%S')] ${GREEN}✅${NC} $*" | tee -a "$LOG_DIR/doctor.log"; }
log_warn() { echo -e "[$(date '+%H:%M:%S')] ${YELLOW}⚠️${NC} $*" | tee -a "$LOG_DIR/doctor.log"; }
log_err()  { echo -e "[$(date '+%H:%M:%S')] ${RED}❌${NC} $*" | tee -a "$LOG_DIR/doctor.log"; }
log_doc()  { echo -e "[$(date '+%H:%M:%S')] ${BLUE}🩺${NC} $*" | tee -a "$LOG_DIR/doctor.log"; }

init_state() {
    if [ ! -f "$STATE_FILE" ]; then
        echo '{"patients":[],"diagnoses":[],"healed":[],"failed":[],"last_check":0}' > "$STATE_FILE"
    fi
}

record_event() {
    local type="$1" adam="$2" desc="$3" action="${4:-}"
    local now; now=$(date +%s)
    python3 -c "
import json
with open('$STATE_FILE') as f:
    state = json.load(f)
entry = {'timestamp': $now, 'adam': '$adam', 'desc': '$desc', 'action': '$action', 'time': '$(date '+%Y-%m-%d %H:%M:%S')'}
state.setdefault('${type}s', []).append(entry)
if len(state['${type}s']) > 200:
    state['${type}s'] = state['${type}s'][-200:]
with open('$STATE_FILE', 'w') as f:
    json.dump(state, f, indent=2)
" 2>/dev/null || true
}

# ─── Lecture de l'état des cron jobs ────────────────────────────
get_adam_status() {
    python3 << 'PYEOF'
import json
with open(__import__('os').path.expanduser('~/.hermes/cron/jobs.json')) as f:
    data = json.load(f)
for job in data.get('jobs', []):
    name = job.get('name', 'unknown')
    status = str(job.get('last_status', '') or '')
    error = (str(job.get('last_error', '') or ''))[:150].replace('|', '/')
    model = str(job.get('model', '') or '')
    provider = str(job.get('provider', '') or '')
    schedule = str(job.get('schedule_display', '') or '')
    enabled = str(job.get('enabled', False))
    script = str(job.get('script', '') or '')
    no_agent = str(job.get('no_agent', False))
    job_id = str(job.get('job_id', ''))
    print(f'{name}\x1f{status}\x1f{error}\x1f{model}\x1f{provider}\x1f{schedule}\x1f{enabled}\x1f{script}\x1f{no_agent}\x1f{job_id}')
PYEOF
}

# ─── Diagnostics par type d'erreur ──────────────────────────────

diagnose_context_error() {
    local adam="$1" error="$2"
    if echo "$error" | grep -qi "context window\|context_length\|64,000\|64000"; then
        echo "DIAGNOSTIC: Context trop court — le modèle local rapporte moins de 64K tokens"
        echo "CAUSE: vLLM configuré avec --max-model-len inférieur à 64K"
        echo "REMEDE: Vérifier config.yaml context_length et --max-model-len du conteneur vLLM"
        return 0
    fi
    return 1
}

diagnose_script_not_found() {
    local adam="$1" error="$2"
    if echo "$error" | grep -qi "Script not found\|No such file"; then
        echo "DIAGNOSTIC: Script manquant"
        echo "CAUSE: Le fichier script n'existe pas dans ~/.hermes/scripts/"
        echo "REMEDE: Copier le script depuis ~/scripts/ vers ~/.hermes/scripts/"
        return 0
    fi
    return 1
}

diagnose_model_error() {
    local adam="$1" error="$2"
    if echo "$error" | grep -qi "model\|connection refused\|Empty response\|timeout"; then
        echo "DIAGNOSTIC: Modèle LLM injoignable"
        echo "CAUSE: vLLM down ou modèle non chargé"
        echo "REMEDE: Vérifier le conteneur vLLM et le redémarrer si nécessaire"
        return 0
    fi
    return 1
}

diagnose_unknown_error() {
    local adam="$1" error="$2"
    echo "DIAGNOSTIC: Erreur non classifiée"
    echo "CAUSE: $error"
    echo "REMEDE: Analyse manuelle requise"
    return 0
}

# ─── Réparations automatiques ───────────────────────────────────

fix_context_error() {
    local adam="$1"
    # Vérifier et corriger config.yaml
    local ctx
    ctx=$(python3 -c "import yaml; c=yaml.safe_load(open('$HOME/.hermes/config.yaml')); print(c.get('model',{}).get('context_length',0))" 2>/dev/null || echo 0)
    if [ "$ctx" -lt 65536 ] 2>/dev/null; then
        python3 -c "
import yaml
with open('$HOME/.hermes/config.yaml', 'r') as f:
    c = yaml.safe_load(f)
if 'model' not in c: c['model'] = {}
c['model']['context_length'] = 65536
if 'delegation' not in c: c['delegation'] = {}
c['delegation']['context_length'] = 65536
with open('$HOME/.hermes/config.yaml', 'w') as f:
    yaml.dump(c, f, default_flow_style=False, allow_unicode=True)
print('config.yaml corrigé')
" 2>/dev/null && echo "FIX: context_length corrigé à 65536" && return 0
    fi
    echo "SKIP: context_length déjà à $ctx — le problème vient du conteneur vLLM"
    return 1
}

fix_script_not_found() {
    local adam="$1" script="$2"
    local script_name=$(basename "$script" 2>/dev/null)
    if [ -z "$script_name" ]; then
        return 1
    fi
    # Chercher le script dans ~/scripts/
    if [ -f "$HOME/scripts/$script_name" ]; then
        cp "$HOME/scripts/$script_name" "$HOME/.hermes/scripts/$script_name"
        chmod +x "$HOME/.hermes/scripts/$script_name"
        echo "FIX: Script $script_name copié vers ~/.hermes/scripts/"
        return 0
    fi
    echo "SKIP: Script $script_name introuvable dans ~/scripts/"
    return 1
}

fix_vllm_down() {
    # Vérifier si le conteneur vLLM tourne
    if ! docker ps --format '{{.Names}}' | grep -q vllm-mistral; then
        echo "FIX: Redémarrage du conteneur vLLM"
        docker start vllm-mistral 2>/dev/null || \
        docker run -d \
            --name vllm-mistral \
            --gpus all \
            --restart unless-stopped \
            -p 8000:8000 \
            -v ~/.cache/huggingface:/root/.cache/huggingface \
            vllm/vllm-openai:v0.8.4 \
            --model stelterlab/Mistral-Small-24B-Instruct-2501-AWQ \
            --gpu-memory-utilization 0.92 \
            --max-model-len 16384 \
            --tensor-parallel-size 1 \
            --host 0.0.0.0 \
            --port 8000 \
            --trust-remote-code \
            --enforce-eager 2>/dev/null
        sleep 10
        if curl -s --max-time 5 http://localhost:8000/v1/models | grep -q "model"; then
            echo "FIX: vLLM redémarré et opérationnel"
            return 0
        fi
        echo "SKIP: vLLM ne répond pas après redémarrage"
        return 1
    fi
    # vLLM tourne mais ne répond pas — le redémarrer
    echo "FIX: Restart du conteneur vLLM"
    docker restart vllm-mistral 2>/dev/null
    sleep 15
    if curl -s --max-time 10 http://localhost:8000/v1/models | grep -q "model" 2>/dev/null; then
        echo "FIX: vLLM redémarré"
        return 0
    fi
    echo "SKIP: vLLM toujours HS après restart"
    return 1
}

# ─── Cycle principal ─────────────────────────────────────────────

run_diagnostic() {
    local do_fix="${1:-false}"
    log "${CYAN}══════════════════════════════════════════════════════════════${NC}"
    log "${CYAN}  ADAM-DOCTOR — Visite médicale — $(date '+%Y-%m-%d %H:%M:%S')${NC}"
    log "${CYAN}══════════════════════════════════════════════════════════════${NC}"
    
    local total=0 ok=0 error_count=0 pending=0
    
    # Récupérer le statut une fois
    local status_output
    status_output=$(get_adam_status)
    
    # Parcourir tous les ADAMs
    while IFS=$'\x1f' read -r name status error model provider schedule enabled script no_agent job_id; do
        [ -z "$name" ] && continue
        total=$((total + 1))
        
        # Convertir enabled en booléen lisible
        if [ "$enabled" = "True" ] || [ "$enabled" = "true" ] || [ "$enabled" = "True" ]; then
            enabled_str="✅ actif"
        else
            enabled_str="❌ désactivé"
        fi
        
        case "$status" in
            ok)
                log_ok "$name — OK ($schedule)"
                ok=$((ok + 1))
                ;;
            error)
                error_count=$((error_count + 1))
                log_err "$name — EN ERREUR"
                log_doc "  Diagnostic de $name..."
                log_doc "  Erreur: $error"
                
                # Envoyer à l'infirmerie = créer un dossier de diagnostic
                local infirmary_path="$INFIRMERY_DIR/$(echo "$name" | tr ' ' '_' | tr '—' '-')"
                mkdir -p "$infirmary_path"
                
                # Diagnose
                local diagnosis=""
                diagnose_context_error "$name" "$error" && diagnosis="context_error" || true
                if [ -z "$diagnosis" ]; then
                    diagnose_script_not_found "$name" "$error" && diagnosis="script_not_found" || true
                fi
                if [ -z "$diagnosis" ]; then
                    diagnose_model_error "$name" "$error" && diagnosis="model_error" || true
                fi
                if [ -z "$diagnosis" ]; then
                    diagnose_unknown_error "$name" "$error"
                    diagnosis="unknown"
                fi
                
                # Écrire le dossier médical
                cat > "$infirmary_path/diagnosis.md" << DIAG
# 🩺 Dossier Médical — $name

**Date :** $(date '+%Y-%m-%d %H:%M:%S')
**Statut :** ERREUR
**Schedule :** $schedule
**Modèle :** $model
**Provider :** $provider
**Script :** $script

## Erreur
$error

## Diagnostic
Type: $diagnosis

## Actions tentées
DIAG
                record_event "patient" "$name" "$diagnosis" "diagnosed"
                
                # Tentative de réparation
                if [ "$do_fix" = "true" ] || [ "$do_fix" = "--fix" ]; then
                    log_doc "  Tentative de soin de $name ($diagnosis)..."
                    local fixed="false"
                    
                    case "$diagnosis" in
                        context_error)
                            fix_context_error "$name" && fixed="true" || true
                            ;;
                        script_not_found)
                            fix_script_not_found "$name" "$script" && fixed="true" || true
                            ;;
                        model_error)
                            fix_vllm_down "$name" && fixed="true" || true
                            ;;
                        unknown)
                            log_doc "  Pas de remède automatique pour $name"
                            ;;
                    esac
                    
                    if [ "$fixed" = "true" ]; then
                        log_ok "  $name SOIGNÉ — relance au prochain cycle"
                        echo "REMEDE: Appliqué avec succès" >> "$infirmary_path/diagnosis.md"
                        record_event "healed" "$name" "$diagnosis" "fixed"
                    else
                        log_warn "  $name toujours malade — surveillance rapprochée"
                        echo "REMEDE: Échec — surveillance requise" >> "$infirmary_path/diagnosis.md"
                        record_event "failed" "$name" "$diagnosis" "failed"
                    fi
                else
                    log_doc "  Mode lecture seule — pas de réparation (lancer avec --fix)"
                fi
                ;;
            None|"")
                pending=$((pending + 1))
                log_doc "$name — jamais lancé ($schedule)"
                ;;
            *)
                log "$name — $status ($schedule)"
                ;;
        esac
    done <<< "$status_output"
    
    # Résumé
    log ""
    log "${CYAN}─── Bilan de santé ───${NC}"
    log_ok "En bonne santé : $ok / $total"
    [ "$error_count" -gt 0 ] && log_err "Malades : $error_count"
    [ "$pending" -gt 0 ] && log_doc "En attente de premier run : $pending"
    
    # Mettre à jour l'état
    python3 -c "
import json, time
with open('$STATE_FILE') as f:
    state = json.load(f)
state['last_check'] = int(time.time())
with open('$STATE_FILE', 'w') as f:
    json.dump(state, f, indent=2)
" 2>/dev/null || true
    
    generate_wiki_report "$total" "$ok" "$error_count" "$pending"
    log_ok "Visite terminée"
    echo ""
}

# ─── Rapport wiki ────────────────────────────────────────────────
generate_wiki_report() {
    local total="$1" ok="$2" err="$3" pending="$4"
    local now; now=$(date '+%Y-%m-%d %H:%M:%S')
    
    local healed_count failed_count
    healed_count=$(python3 -c "import json; s=json.load(open('$STATE_FILE')); print(len(s.get('healed',[])))" 2>/dev/null || echo 0)
    failed_count=$(python3 -c "import json; s=json.load(open('$STATE_FILE')); print(len(s.get('failed',[])))" 2>/dev/null || echo 0)
    
    cat > "$WIKI_FILE" << WIKIEOF
---
title: ADAM-DOCTOR — Médecin de l'équipe
type: entity
created: 2026-07-22
tags: [adam, doctor, medical, resilience, repair, infirmary]
importance: 1
domain: [devops, monitoring]
related: ["adam-praetor", "adam-blue", "adam-team"]
---

# 🩺 ADAM-DOCTOR — Médecin de l'Équipe ADAM

> Dernière visite : $now
> État global : $ok/$total en bonne santé, $err malade(s), $pending en attente

## Bilan de Santé

| Métrique | Valeur |
|----------|--------|
| ADAMs surveillés | $total |
| En bonne santé | $ok ✅ |
| Malades | $err ❌ |
| Jamais lancés | $pending ⏳ |
| Soignés (total) | $healed_count 🩹 |
| Échecs de soin (total) | $failed_count ⚠️ |

## Infirmerie

Les ADAMs en erreur sont diagnostiqués et envoyés à l'infirmerie :
\`~/.doctor/infirmary/\`

Chaque patient a un dossier médical (\`diagnosis.md\`) avec :
- L'erreur détectée
- Le diagnostic (type d'erreur)
- Les remèdes tentés

## Types de diagnostics

| Type | Cause | Remède automatique |
|------|-------|---------------------|
| context_error | Context < 64K | Corrige config.yaml |
| script_not_found | Script manquant | Copie depuis ~/scripts/ |
| model_error | vLLM down | Redémarre le conteneur |
| unknown | Erreur non classée | Analyse manuelle |

## Derniers Soins

WIKIEOF

    python3 -c "
import json
with open('$STATE_FILE') as f:
    state = json.load(f)
icons = {'healed': '🩹', 'failed': '⚠️', 'patient': '🩺'}
for e in reversed(state.get('healed', [])[-10:]):
    print(f\"| {e['time']} | {e['adam']} | {e['desc']} | 🩹 SOIGNÉ |\")
for e in reversed(state.get('failed', [])[-10:]):
    print(f\"| {e['time']} | {e['adam']} | {e['desc']} | ⚠️ ÉCHEC |\")
" 2>/dev/null >> "$WIKI_FILE" || true

    echo "" >> "$WIKI_FILE"
    echo "---" >> "$WIKI_FILE"
    echo "*Généré par ADAM-DOCTOR — $now*" >> "$WIKI_FILE"
    
    log "Rapport wiki: $WIKI_FILE"
}

# ─── Point d'entrée ─────────────────────────────────────────────
main() {
    init_state
    case "${1:-}" in
        --once) run_diagnostic false ;;
        --fix)  run_diagnostic true ;;
        *)
            log "${CYAN}ADAM-DOCTOR — Surveillance médicale continue (5 min)${NC}"
            while true; do run_diagnostic true; sleep 300; done
            ;;
    esac
}

main "$@"
