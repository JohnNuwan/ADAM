# Auto-amélioration de adam-ctf
# Demande: Ajouter un logging des appels d'outils
# Date: 2026-07-25T23:44:02.900923
import logging
log = logging.getLogger(__name__)
def log_call(name, result):
    log.info(f'Tool {name}: {result}')
