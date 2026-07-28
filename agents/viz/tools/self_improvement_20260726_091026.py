# Auto-amélioration de adam-viz
# Demande: Optimiser la gestion d'erreur des outils
# Date: 2026-07-26T09:10:26.337301
def safe_exec(func):
    try: return func()
    except Exception as e: return {'error': str(e)}
