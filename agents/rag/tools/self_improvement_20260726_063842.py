# Auto-amélioration de adam-rag
# Demande: Optimiser la gestion d'erreur des outils
# Date: 2026-07-26T06:38:42.900226
def safe_exec(func):
    try: return func()
    except Exception as e: return {'error': str(e)}
