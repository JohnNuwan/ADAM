# Auto-amélioration de adam-skillsmith
# Demande: Optimiser la gestion d'erreur des outils
# Date: 2026-07-26T00:26:38.603045
def safe_exec(func):
    try: return func()
    except Exception as e: return {'error': str(e)}
