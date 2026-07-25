# Auto-amélioration de adam-scribe
# Demande: Ajouter un logging des appels d'outils
# Date: 2026-07-25T23:19:31.220914
import logging
log = logging.getLogger(__name__)
def log_call(name, result):
    log.info(f'Tool {name}: {result}')
