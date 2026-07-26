# Auto-amélioration de adam-social
# Demande: Ajouter un cache aux outils pour éviter les appels dupliqués
# Date: 2026-07-26T02:02:49.726606
CACHE = {}
def cached_call(key, func, *args):
    if key not in CACHE:
        CACHE[key] = func(*args)
    return CACHE[key]
