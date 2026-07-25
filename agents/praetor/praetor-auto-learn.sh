# =============================================================================
# ADAM-PRAETOR — Règles d'auto-apprentissage et correction
# =============================================================================
# Chaque règle = pattern d'erreur → correction automatique
# Généré par analyse des logs le 2026-07-22
# =============================================================================

RULES_FILE="$HOME/.praetor/rules.json"
LOG_DIR="$HOME/.praetor/logs"

mkdir -p "$(dirname "$RULES_FILE")"

# ─── Règles de correction pré-définies ──────────────────────────────────────

cat > "$RULES_FILE" << 'RULES'
{
  "version": "1.0",
  "generated": "2026-07-22",
  "rules": [
    {
      "id": "rule-001",
      "pattern": "port_in_use|Address already in use",
      "description": "Port déjà occupé → tuer l'ancien processus et relancer",
      "severity": "warning",
      "correction": "fuser -k PORT/tcp; sleep 2",
      "source": "logs_agent",
      "first_seen": "2026-07-22"
    },
    {
      "id": "rule-002",
      "pattern": "No module named 'pandas'",
      "description": "Dépendance Python manquante → installer avec pip",
      "severity": "warning",
      "correction": "pip install pandas",
      "source": "logs_errors",
      "first_seen": "2026-07-22"
    },
    {
      "id": "rule-003",
      "pattern": "No module named 'agent.helios_constants'",
      "description": "Module hélios introuvable → outil obsolète, à supprimer",
      "severity": "info",
      "correction": "hermes tools disable",
      "source": "logs_errors",
      "first_seen": "2026-07-22"
    },
    {
      "id": "rule-004",
      "pattern": "No such file or directory: 'uvx'",
      "description": "uvx introuvable → installer avec npm/cargo",
      "severity": "warning",
      "correction": "npm install -g @modelcontextprotocol/server-everything || cargo install uvx",
      "source": "logs_mcp",
      "first_seen": "2026-07-22"
    },
    {
      "id": "rule-005",
      "pattern": "gateway.exit_nonzero|SystemExit: 75",
      "description": "Gateway crash → redémarrer la passerelle",
      "severity": "error",
      "correction": "hermes gateway restart",
      "source": "logs_gateway",
      "first_seen": "2026-07-22"
    },
    {
      "id": "rule-006",
      "pattern": "unhealthy",
      "description": "Conteneur Docker unhealthy → redémarrer",
      "severity": "warning",
      "correction": "docker restart CONTAINER",
      "source": "logs_docker",
      "first_seen": "2026-07-22"
    },
    {
      "id": "rule-007",
      "pattern": "no Nous authentication found",
      "description": "Auth Nous manquante → configurer ou désactiver feature",
      "severity": "info",
      "correction": "hermes auth nous",
      "source": "logs_errors",
      "first_seen": "2026-07-22"
    },
    {
      "id": "rule-008",
      "pattern": "HTTP 000|Connexion refusée",
      "description": "Serveur injoignable → tuer et relancer",
      "severity": "error",
      "correction": "PRACTOR_RESTART",
      "source": "praetor_diagnostic",
      "first_seen": "2026-07-22"
    },
    {
      "id": "rule-009",
      "pattern": "HTTP 50[0-9]",
      "description": "Erreur serveur 5xx → redémarrer l'application",
      "severity": "error",
      "correction": "PRACTOR_RESTART",
      "source": "praetor_diagnostic",
      "first_seen": "2026-07-22"
    },
    {
      "id": "rule-010",
      "pattern": "Puppeteer MCP Server closed",
      "description": "Serveur MCP Puppeteer fermé → relancer via MCP config",
      "severity": "warning",
      "correction": "hermes mcp restart puppeteer",
      "source": "logs_mcp",
      "first_seen": "2026-07-22"
    },
    {
      "id": "rule-011",
      "pattern": "check_fn.*returned False",
      "description": "Prérequis d'outil non satisfait → vérifier config",
      "severity": "info",
      "correction": "CHECK_CONFIG",
      "source": "logs_errors",
      "first_seen": "2026-07-22"
    }
  ]
}
RULES

echo "✅ Règles d'auto-apprentissage créées: $RULES_FILE"
echo "   $(python3 -c "import json; r=json.load(open('$RULES_FILE')); print(f\"{len(r['rules'])} règles de correction\")")"

# ─── Fonction d'analyse des logs ────────────────────────────────────────────
# Ajoutée au script praetor-watch.sh pour l'auto-apprentissage

cat >> "$HOME/scripts/praetor-watch.sh" << 'APPEND'

# ─── Auto-apprentissage : analyse des logs ──────────────────────────────────

RULES_FILE="$HOME/.praetor/rules.json"
LEARNED_RULES_FILE="$HOME/.praetor/learned_rules.json"

learn_from_logs() {
    """Analyse les logs récents et crée de nouvelles règles de correction."""
    local log_dir="$HOME/.hermes/logs"
    local new_rules=0
    
    mkdir -p "$(dirname "$LEARNED_RULES_FILE")"
    
    # Charger les règles existantes
    local existing_patterns
    existing_patterns=$(python3 -c "
import json
try:
    with open('$RULES_FILE') as f:
        rules = json.load(f)
    print(' '.join([r['pattern'] for r in rules['rules']]))
except:
    print('')
" 2>/dev/null)
    
    # Analyser les logs d'erreur récents
    for logfile in "$log_dir"/*.log; do
        [ -f "$logfile" ] || continue
        
        # Extraire les patterns d'erreur inconnus
        python3 -c "
import json, re, os
from collections import Counter

logfile = '$logfile'
existing = '$existing_patterns'.split()
rules_file = '$LEARNED_RULES_FILE'

# Patterns d'erreur courants
error_patterns = [
    (r'ERROR\\s+(.*)', 'error'),
    (r'Traceback \\(most recent call last\\)', 'traceback'),
    (r'FileNotFoundError:\\s+(.*)', 'file_not_found'),
    (r'ConnectionError:\\s+(.*)', 'connection_error'),
    (r'TimeoutError:\\s+(.*)', 'timeout_error'),
    (r'ImportError:\\s+(.*)', 'import_error'),
    (r'ModuleNotFoundError:\\s+(.*)', 'module_missing'),
    (r'PermissionError:\\s+(.*)', 'permission_error'),
    (r'OSError:\\s+(.*)', 'os_error'),
    (r'ValueError:\\s+(.*)', 'value_error'),
    (r'KeyError:\\s+(.*)', 'key_error'),
]

errors_found = Counter()

try:
    with open(logfile) as f:
        for line in f:
            for pattern, etype in error_patterns:
                m = re.search(pattern, line)
                if m:
                    errors_found[etype] += 1
except:
    pass

# Charger les règles apprises existantes
learned = {}
if os.path.exists(rules_file):
    try:
        with open(rules_file) as f:
            learned = json.load(f)
    except:
        pass

if 'rules' not in learned:
    learned['rules'] = []
if 'version' not in learned:
    learned['version'] = '1.0'
    learned['generated'] = '2026-07-22'

# Ajouter les nouvelles erreurs récurrentes
known_patterns = set(existing)
for etype, count in errors_found.most_common(5):
    if count >= 3 and etype not in known_patterns:
        learned['rules'].append({
            'id': f'learned-{len(learned[\"rules\"])+1:03d}',
            'pattern': etype,
            'description': f'Erreur {etype} détectée {count} fois dans {os.path.basename(logfile)}',
            'severity': 'warning',
            'correction': 'ANALYZE',
            'source': os.path.basename(logfile),
            'first_seen': '2026-07-22',
            'occurrences': count,
        })

with open(rules_file, 'w') as f:
    json.dump(learned, f, indent=2)
" 2>/dev/null || true
    done
}

# Ajouter l'apprentissage à la fin du cycle de diagnostic
# S'exécute après chaque diagnostic
learn_from_logs
APPEND

echo "✅ Module d'auto-apprentissage ajouté au script praetor-watch.sh"