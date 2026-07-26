# Auto-amélioration de adam-red-team
# Demande: Optimiser la gestion d'erreur des outils
# Date: 2026-07-26T05:22:35.121406
def safe_exec(func):
    try: return func()
    except Exception as e: return {'error': str(e)}
