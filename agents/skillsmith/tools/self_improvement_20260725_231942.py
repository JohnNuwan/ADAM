# Auto-amélioration de adam-skillsmith
# Demande: Optimiser la gestion d'erreur des outils
# Date: 2026-07-25T23:19:42.451721
def safe_exec(func):
    try: return func()
    except Exception as e: return {'error': str(e)}
