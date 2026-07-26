# Auto-amélioration de adam-ctf
# Demande: Ajouter un logging des appels d'outils
# Date: 2026-07-26T06:55:16.504855
import logging
log = logging.getLogger(__name__)
def log_call(name, result):
    log.info(f'Tool {name}: {result}')
