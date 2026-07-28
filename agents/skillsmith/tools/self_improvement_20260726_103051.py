# Auto-amélioration de adam-skillsmith
# Demande: Ajouter un logging des appels d'outils
# Date: 2026-07-26T10:30:51.691230
import logging
log = logging.getLogger(__name__)
def log_call(name, result):
    log.info(f'Tool {name}: {result}')
