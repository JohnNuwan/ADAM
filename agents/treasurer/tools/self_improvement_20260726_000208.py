# Auto-amélioration de adam-treasurer
# Demande: Optimiser la gestion d'erreur des outils
# Date: 2026-07-26T00:02:08.838907
def safe_exec(func):
    try: return func()
    except Exception as e: return {'error': str(e)}
