# Auto-amélioration de adam-treasurer
# Demande: Ajouter un cache aux outils pour éviter les appels dupliqués
# Date: 2026-07-26T01:52:59.889269
CACHE = {}
def cached_call(key, func, *args):
    if key not in CACHE:
        CACHE[key] = func(*args)
    return CACHE[key]
