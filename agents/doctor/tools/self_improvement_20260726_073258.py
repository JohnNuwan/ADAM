# Auto-amélioration de adam-doctor
# Demande: Optimiser la gestion d'erreur des outils
# Date: 2026-07-26T07:32:58.299365
def safe_exec(func):
    try: return func()
    except Exception as e: return {'error': str(e)}
