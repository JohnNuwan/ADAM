# Auto-amélioration de adam-praetor
# Demande: Optimiser la gestion d'erreur des outils
# Date: 2026-07-26T04:20:52.149663
def safe_exec(func):
    try: return func()
    except Exception as e: return {'error': str(e)}
