# Auto-amélioration de adam-critic
# Demande: Ajouter un cache aux outils pour éviter les appels dupliqués
# Date: 2026-07-26T03:17:04.522817
CACHE = {}
def cached_call(key, func, *args):
    if key not in CACHE:
        CACHE[key] = func(*args)
    return CACHE[key]
