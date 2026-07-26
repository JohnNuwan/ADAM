# Auto-amélioration de adam-blue-team
# Demande: Optimiser la gestion d'erreur des outils
# Date: 2026-07-26T06:50:10.630508
def safe_exec(func):
    try: return func()
    except Exception as e: return {'error': str(e)}
