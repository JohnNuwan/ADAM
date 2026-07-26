# Auto-amélioration de adam-critic
# Demande: Optimiser la gestion d'erreur des outils
# Date: 2026-07-26T07:18:16.506618
def safe_exec(func):
    try: return func()
    except Exception as e: return {'error': str(e)}
