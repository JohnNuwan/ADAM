# Auto-amélioration de adam-scribe
# Demande: Optimiser la gestion d'erreur des outils
# Date: 2026-07-26T12:00:15.472609
def safe_exec(func):
    try: return func()
    except Exception as e: return {'error': str(e)}
