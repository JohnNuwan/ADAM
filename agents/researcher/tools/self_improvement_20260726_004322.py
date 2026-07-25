# Auto-amélioration de adam-researcher
# Demande: Ajouter un logging des appels d'outils
# Date: 2026-07-26T00:43:22.065195
import logging
log = logging.getLogger(__name__)
def log_call(name, result):
    log.info(f'Tool {name}: {result}')
