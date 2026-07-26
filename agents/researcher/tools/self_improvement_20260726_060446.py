# Auto-amélioration de adam-researcher
# Demande: Ajouter un cache aux outils pour éviter les appels dupliqués
# Date: 2026-07-26T06:04:46.624897
CACHE = {}
def cached_call(key, func, *args):
    if key not in CACHE:
        CACHE[key] = func(*args)
    return CACHE[key]
