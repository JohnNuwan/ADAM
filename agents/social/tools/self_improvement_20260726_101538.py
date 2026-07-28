# Auto-amélioration de adam-social
# Demande: Optimiser la gestion d'erreur des outils
# Date: 2026-07-26T10:15:38.792690
def safe_exec(func):
    try: return func()
    except Exception as e: return {'error': str(e)}
