# Auto-amélioration de adam-scribe
# Demande: Optimiser la gestion d'erreur des outils
# Date: 2026-07-26T06:20:49.641638
def safe_exec(func):
    try: return func()
    except Exception as e: return {'error': str(e)}
