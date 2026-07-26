# Auto-amélioration de adam-social
# Demande: Ajouter un cache aux outils pour éviter les appels dupliqués
# Date: 2026-07-26T04:38:43.877110
CACHE = {}
def cached_call(key, func, *args):
    if key not in CACHE:
        CACHE[key] = func(*args)
    return CACHE[key]
