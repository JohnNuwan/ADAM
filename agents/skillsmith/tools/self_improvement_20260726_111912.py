# Auto-amélioration de adam-skillsmith
# Demande: Ajouter un logging des appels d'outils
# Date: 2026-07-26T11:19:12.217497
import logging
log = logging.getLogger(__name__)
def log_call(name, result):
    log.info(f'Tool {name}: {result}')
