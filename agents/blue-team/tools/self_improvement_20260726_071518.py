# Auto-amélioration de adam-blue-team
# Demande: Ajouter un logging des appels d'outils
# Date: 2026-07-26T07:15:18.078263
import logging
log = logging.getLogger(__name__)
def log_call(name, result):
    log.info(f'Tool {name}: {result}')
