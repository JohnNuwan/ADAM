# Auto-amélioration de adam-blue-team
# Demande: Optimiser la gestion d'erreur des outils
# Date: 2026-07-26T04:40:28.865936
def safe_exec(func):
    try: return func()
    except Exception as e: return {'error': str(e)}
