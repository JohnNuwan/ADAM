# Auto-amélioration de adam-sentinel
# Demande: Optimiser la gestion d'erreur des outils
# Date: 2026-07-26T03:42:56.905893
def safe_exec(func):
    try: return func()
    except Exception as e: return {'error': str(e)}
