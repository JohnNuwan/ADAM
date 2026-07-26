# Auto-amélioration de adam-blue-team
# Demande: Ajouter un logging des appels d'outils
# Date: 2026-07-26T03:26:07.808505
import logging
log = logging.getLogger(__name__)
def log_call(name, result):
    log.info(f'Tool {name}: {result}')
