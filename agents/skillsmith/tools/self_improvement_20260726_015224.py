# Auto-amélioration de adam-skillsmith
# Demande: Optimiser la gestion d'erreur des outils
# Date: 2026-07-26T01:52:24.958395
def safe_exec(func):
    try: return func()
    except Exception as e: return {'error': str(e)}
