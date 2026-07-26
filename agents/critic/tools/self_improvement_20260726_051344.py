# Auto-amélioration de adam-critic
# Demande: Ajouter un logging des appels d'outils
# Date: 2026-07-26T05:13:44.935243
import logging
log = logging.getLogger(__name__)
def log_call(name, result):
    log.info(f'Tool {name}: {result}')
