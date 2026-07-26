# Auto-amélioration de adam-rag
# Demande: Ajouter un logging des appels d'outils
# Date: 2026-07-26T04:59:09.353818
import logging
log = logging.getLogger(__name__)
def log_call(name, result):
    log.info(f'Tool {name}: {result}')
