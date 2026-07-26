# Auto-amélioration de adam-verifier
# Demande: Optimiser la gestion d'erreur des outils
# Date: 2026-07-26T07:41:02.257405
def safe_exec(func):
    try: return func()
    except Exception as e: return {'error': str(e)}
