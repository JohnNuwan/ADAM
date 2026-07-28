# Auto-amélioration de adam-scribe
# Demande: Ajouter un cache aux outils pour éviter les appels dupliqués
# Date: 2026-07-26T09:38:57.808973
CACHE = {}
def cached_call(key, func, *args):
    if key not in CACHE:
        CACHE[key] = func(*args)
    return CACHE[key]
