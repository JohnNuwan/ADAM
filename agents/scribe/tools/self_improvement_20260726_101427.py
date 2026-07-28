# Auto-amélioration de adam-scribe
# Demande: Optimiser la gestion d'erreur des outils
# Date: 2026-07-26T10:14:27.609392
def safe_exec(func):
    try: return func()
    except Exception as e: return {'error': str(e)}
