# Auto-amélioration de adam-red-team
# Demande: Ajouter un logging des appels d'outils
# Date: 2026-07-26T03:46:41.034380
import logging
log = logging.getLogger(__name__)
def log_call(name, result):
    log.info(f'Tool {name}: {result}')
