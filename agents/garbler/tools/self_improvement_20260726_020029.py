# Auto-amélioration de adam-garbler
# Demande: Ajouter un logging des appels d'outils
# Date: 2026-07-26T02:00:29.729386
import logging
log = logging.getLogger(__name__)
def log_call(name, result):
    log.info(f'Tool {name}: {result}')
