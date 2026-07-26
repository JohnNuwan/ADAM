# Auto-amélioration de adam-sentinel
# Demande: Optimiser la gestion d'erreur des outils
# Date: 2026-07-26T02:30:13.161063
def safe_exec(func):
    try: return func()
    except Exception as e: return {'error': str(e)}
