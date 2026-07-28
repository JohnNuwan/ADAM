# Auto-amélioration de adam-scribe
# Demande: Ajouter un cache aux outils pour éviter les appels dupliqués
# Date: 2026-07-26T10:52:13.515732
CACHE = {}
def cached_call(key, func, *args):
    if key not in CACHE:
        CACHE[key] = func(*args)
    return CACHE[key]
