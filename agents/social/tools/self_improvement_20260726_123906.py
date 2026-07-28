# Auto-amélioration de adam-social
# Demande: Optimiser la gestion d'erreur des outils
# Date: 2026-07-26T12:39:06.880004
def safe_exec(func):
    try: return func()
    except Exception as e: return {'error': str(e)}
