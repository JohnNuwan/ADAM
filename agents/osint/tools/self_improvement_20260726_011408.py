# Auto-amélioration de adam-osint
# Demande: Ajouter un logging des appels d'outils
# Date: 2026-07-26T01:14:08.838777
import logging
log = logging.getLogger(__name__)
def log_call(name, result):
    log.info(f'Tool {name}: {result}')
