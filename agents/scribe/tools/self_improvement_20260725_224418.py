# Auto-amélioration de adam-scribe
# Demande: Optimiser la gestion d'erreur des outils
# Date: 2026-07-25T22:44:18.096030
def safe_exec(func):
    try: return func()
    except Exception as e: return {'error': str(e)}
