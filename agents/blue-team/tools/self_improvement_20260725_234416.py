# Auto-amélioration de adam-blue-team
# Demande: Optimiser la gestion d'erreur des outils
# Date: 2026-07-25T23:44:16.133922
def safe_exec(func):
    try: return func()
    except Exception as e: return {'error': str(e)}
