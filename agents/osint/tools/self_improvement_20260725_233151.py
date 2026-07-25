# Auto-amélioration de adam-osint
# Demande: Optimiser la gestion d'erreur des outils
# Date: 2026-07-25T23:31:51.429728
def safe_exec(func):
    try: return func()
    except Exception as e: return {'error': str(e)}
