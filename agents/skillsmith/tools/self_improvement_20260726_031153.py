# Auto-amélioration de adam-skillsmith
# Demande: Optimiser la gestion d'erreur des outils
# Date: 2026-07-26T03:11:53.398834
def safe_exec(func):
    try: return func()
    except Exception as e: return {'error': str(e)}
