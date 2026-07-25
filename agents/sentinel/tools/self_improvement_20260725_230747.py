# Auto-amélioration de adam-sentinel
# Demande: Optimiser la gestion d'erreur des outils
# Date: 2026-07-25T23:07:47.193556
def safe_exec(func):
    try: return func()
    except Exception as e: return {'error': str(e)}
