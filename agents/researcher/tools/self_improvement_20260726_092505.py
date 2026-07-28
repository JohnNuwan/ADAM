# Auto-amélioration de adam-researcher
# Demande: Optimiser la gestion d'erreur des outils
# Date: 2026-07-26T09:25:05.710245
def safe_exec(func):
    try: return func()
    except Exception as e: return {'error': str(e)}
