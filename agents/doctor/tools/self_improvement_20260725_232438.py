# Auto-amélioration de adam-doctor
# Demande: Ajouter un logging des appels d'outils
# Date: 2026-07-25T23:24:38.365610
import logging
log = logging.getLogger(__name__)
def log_call(name, result):
    log.info(f'Tool {name}: {result}')
