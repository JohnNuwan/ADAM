# Auto-amélioration de adam-praetor
# Demande: Optimiser la gestion d'erreur des outils
# Date: 2026-07-25T22:42:45.919789
def safe_exec(func):
    try: return func()
    except Exception as e: return {'error': str(e)}
