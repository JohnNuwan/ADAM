# Auto-amélioration de adam-treasurer
# Demande: Optimiser la gestion d'erreur des outils
# Date: 2026-07-26T02:54:25.778175
def safe_exec(func):
    try: return func()
    except Exception as e: return {'error': str(e)}
