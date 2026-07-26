# Auto-amélioration de adam-garbler
# Demande: Optimiser la gestion d'erreur des outils
# Date: 2026-07-26T07:11:03.568547
def safe_exec(func):
    try: return func()
    except Exception as e: return {'error': str(e)}
