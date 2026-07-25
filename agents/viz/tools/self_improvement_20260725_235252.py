# Auto-amélioration de adam-viz
# Demande: Ajouter un logging des appels d'outils
# Date: 2026-07-25T23:52:52.147173
import logging
log = logging.getLogger(__name__)
def log_call(name, result):
    log.info(f'Tool {name}: {result}')
