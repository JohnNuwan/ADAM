# Auto-amélioration de adam-rag
# Demande: Ajouter un logging des appels d'outils
# Date: 2026-07-26T10:05:14.089660
import logging
log = logging.getLogger(__name__)
def log_call(name, result):
    log.info(f'Tool {name}: {result}')
