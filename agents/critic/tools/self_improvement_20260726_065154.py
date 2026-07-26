# Auto-amélioration de adam-critic
# Demande: Ajouter un cache aux outils pour éviter les appels dupliqués
# Date: 2026-07-26T06:51:54.580504
CACHE = {}
def cached_call(key, func, *args):
    if key not in CACHE:
        CACHE[key] = func(*args)
    return CACHE[key]
