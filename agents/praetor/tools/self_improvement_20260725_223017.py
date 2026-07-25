# Auto-amélioration de adam-praetor
# Demande: Ajouter un logging des appels d'outils
# Date: 2026-07-25T22:30:17.628963
import logging
log = logging.getLogger(__name__)
def log_call(name, result):
    log.info(f'Tool {name}: {result}')
