# Auto-amélioration de adam-red-team
# Demande: Ajouter un cache aux outils pour éviter les appels dupliqués
# Date: 2026-07-26T11:36:03.705098
CACHE = {}
def cached_call(key, func, *args):
    if key not in CACHE:
        CACHE[key] = func(*args)
    return CACHE[key]
