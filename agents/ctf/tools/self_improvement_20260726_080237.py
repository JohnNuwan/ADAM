# Auto-amélioration de adam-ctf
# Demande: Optimiser la gestion d'erreur des outils
# Date: 2026-07-26T08:02:37.805476
def safe_exec(func):
    try: return func()
    except Exception as e: return {'error': str(e)}
