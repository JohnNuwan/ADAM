# Auto-amélioration de adam-sentinel
# Demande: Ajouter un logging des appels d'outils
# Date: 2026-07-26T06:00:41.754118
import logging
log = logging.getLogger(__name__)
def log_call(name, result):
    log.info(f'Tool {name}: {result}')
