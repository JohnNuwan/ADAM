# Auto-amélioration de adam-scribe
# Demande: Ajouter un logging des appels d'outils
# Date: 2026-07-26T05:45:27.985348
import logging
log = logging.getLogger(__name__)
def log_call(name, result):
    log.info(f'Tool {name}: {result}')
