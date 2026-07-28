# Auto-amélioration de adam-viz
# Demande: Optimiser la gestion d'erreur des outils
# Date: 2026-07-26T09:03:25.916980
def safe_exec(func):
    try: return func()
    except Exception as e: return {'error': str(e)}
