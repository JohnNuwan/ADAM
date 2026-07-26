# Auto-amélioration de adam-osint
# Demande: Optimiser la gestion d'erreur des outils
# Date: 2026-07-26T06:17:16.007985
def safe_exec(func):
    try: return func()
    except Exception as e: return {'error': str(e)}
