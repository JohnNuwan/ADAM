# Auto-amélioration de adam-social
# Demande: Ajouter un logging des appels d'outils
# Date: 2026-07-26T05:20:46.463304
import logging
log = logging.getLogger(__name__)
def log_call(name, result):
    log.info(f'Tool {name}: {result}')
