# Auto-amélioration de adam-ctf
# Demande: Ajouter un logging des appels d'outils
# Date: 2026-07-26T08:54:02.453995
import logging
log = logging.getLogger(__name__)
def log_call(name, result):
    log.info(f'Tool {name}: {result}')
