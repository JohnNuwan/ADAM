# Auto-amélioration de adam-treasurer
# Demande: Optimiser la gestion d'erreur des outils
# Date: 2026-07-25T23:56:05.373187
def safe_exec(func):
    try: return func()
    except Exception as e: return {'error': str(e)}
