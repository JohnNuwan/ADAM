# Auto-amélioration de adam-doctor
# Demande: Optimiser la gestion d'erreur des outils
# Date: 2026-07-26T03:12:12.893553
def safe_exec(func):
    try: return func()
    except Exception as e: return {'error': str(e)}
