# Auto-amélioration de adam-social
# Demande: Ajouter un logging des appels d'outils
# Date: 2026-07-26T00:43:04.617489
import logging
log = logging.getLogger(__name__)
def log_call(name, result):
    log.info(f'Tool {name}: {result}')
