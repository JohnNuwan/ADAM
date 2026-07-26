# Auto-amélioration de adam-sentinel
# Demande: Ajouter un cache aux outils pour éviter les appels dupliqués
# Date: 2026-07-26T02:17:08.762523
CACHE = {}
def cached_call(key, func, *args):
    if key not in CACHE:
        CACHE[key] = func(*args)
    return CACHE[key]
