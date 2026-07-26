# Auto-amélioration de adam-scribe
# Demande: Ajouter un cache aux outils pour éviter les appels dupliqués
# Date: 2026-07-26T02:01:53.144388
CACHE = {}
def cached_call(key, func, *args):
    if key not in CACHE:
        CACHE[key] = func(*args)
    return CACHE[key]
