# Auto-amélioration de adam-skillsmith
# Demande: Optimiser la gestion d'erreur des outils
# Date: 2026-07-26T12:01:00.536683
def safe_exec(func):
    try: return func()
    except Exception as e: return {'error': str(e)}
