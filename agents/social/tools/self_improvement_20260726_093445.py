# Auto-amélioration de adam-social
# Demande: Ajouter un logging des appels d'outils
# Date: 2026-07-26T09:34:45.798430
import logging
log = logging.getLogger(__name__)
def log_call(name, result):
    log.info(f'Tool {name}: {result}')
