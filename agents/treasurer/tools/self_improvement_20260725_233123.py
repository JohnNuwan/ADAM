# Auto-amélioration de adam-treasurer
# Demande: Optimiser la gestion d'erreur des outils
# Date: 2026-07-25T23:31:23.090005
def safe_exec(func):
    try: return func()
    except Exception as e: return {'error': str(e)}
