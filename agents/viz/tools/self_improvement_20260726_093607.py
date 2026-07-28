# Auto-amélioration de adam-viz
# Demande: Ajouter un logging des appels d'outils
# Date: 2026-07-26T09:36:07.624069
import logging
log = logging.getLogger(__name__)
def log_call(name, result):
    log.info(f'Tool {name}: {result}')
