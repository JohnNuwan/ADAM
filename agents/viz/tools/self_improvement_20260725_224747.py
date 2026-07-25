# Auto-amélioration de adam-viz
# Demande: Ajouter un cache aux outils pour éviter les appels dupliqués
# Date: 2026-07-25T22:47:47.419003
CACHE = {}
def cached_call(key, func, *args):
    if key not in CACHE:
        CACHE[key] = func(*args)
    return CACHE[key]
