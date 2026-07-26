# Auto-amélioration de adam-rag
# Demande: Optimiser la gestion d'erreur des outils
# Date: 2026-07-26T02:15:21.163314
def safe_exec(func):
    try: return func()
    except Exception as e: return {'error': str(e)}
