# Auto-amélioration de adam-treasurer
# Demande: Ajouter un logging des appels d'outils
# Date: 2026-07-26T03:01:44.898759
import logging
log = logging.getLogger(__name__)
def log_call(name, result):
    log.info(f'Tool {name}: {result}')
