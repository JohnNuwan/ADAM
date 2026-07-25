# Auto-amélioration de adam-skillsmith
# Demande: Ajouter un cache aux outils pour éviter les appels dupliqués
# Date: 2026-07-25T23:15:00.268560
CACHE = {}
def cached_call(key, func, *args):
    if key not in CACHE:
        CACHE[key] = func(*args)
    return CACHE[key]
