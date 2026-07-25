# Auto-amélioration de adam-blue-team
# Demande: Ajouter un logging des appels d'outils
# Date: 2026-07-25T22:58:27.101246
import logging
log = logging.getLogger(__name__)
def log_call(name, result):
    log.info(f'Tool {name}: {result}')
