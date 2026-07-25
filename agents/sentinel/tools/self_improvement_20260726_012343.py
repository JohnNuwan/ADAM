# Auto-amélioration de adam-sentinel
# Demande: Ajouter un logging des appels d'outils
# Date: 2026-07-26T01:23:43.228128
import logging
log = logging.getLogger(__name__)
def log_call(name, result):
    log.info(f'Tool {name}: {result}')
