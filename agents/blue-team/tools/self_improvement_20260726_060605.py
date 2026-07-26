# Auto-amélioration de adam-blue-team
# Demande: Ajouter un cache aux outils pour éviter les appels dupliqués
# Date: 2026-07-26T06:06:05.409149
CACHE = {}
def cached_call(key, func, *args):
    if key not in CACHE:
        CACHE[key] = func(*args)
    return CACHE[key]
