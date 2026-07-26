# Auto-amélioration de adam-red-team
# Demande: Optimiser la gestion d'erreur des outils
# Date: 2026-07-26T02:05:21.552840
def safe_exec(func):
    try: return func()
    except Exception as e: return {'error': str(e)}
