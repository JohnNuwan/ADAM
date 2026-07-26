# Auto-amélioration de adam-ctf
# Demande: Optimiser la gestion d'erreur des outils
# Date: 2026-07-26T05:43:01.581788
def safe_exec(func):
    try: return func()
    except Exception as e: return {'error': str(e)}
