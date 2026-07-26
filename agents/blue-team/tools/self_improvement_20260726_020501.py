# Auto-amélioration de adam-blue-team
# Demande: Ajouter un cache aux outils pour éviter les appels dupliqués
# Date: 2026-07-26T02:05:01.694634
CACHE = {}
def cached_call(key, func, *args):
    if key not in CACHE:
        CACHE[key] = func(*args)
    return CACHE[key]
