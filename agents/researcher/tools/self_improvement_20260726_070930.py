# Auto-amélioration de adam-researcher
# Demande: Optimiser la gestion d'erreur des outils
# Date: 2026-07-26T07:09:30.245591
def safe_exec(func):
    try: return func()
    except Exception as e: return {'error': str(e)}
