# Auto-amélioration de adam-praetor
# Demande: Ajouter un logging des appels d'outils
# Date: 2026-07-26T04:41:20.463599
import logging
log = logging.getLogger(__name__)
def log_call(name, result):
    log.info(f'Tool {name}: {result}')
