# Auto-amélioration de adam-osint
# Demande: Optimiser la gestion d'erreur des outils
# Date: 2026-07-26T11:33:58.767987
def safe_exec(func):
    try: return func()
    except Exception as e: return {'error': str(e)}
