# Auto-amélioration de adam-doctor
# Demande: Ajouter un cache aux outils pour éviter les appels dupliqués
# Date: 2026-07-26T00:01:59.338649
CACHE = {}
def cached_call(key, func, *args):
    if key not in CACHE:
        CACHE[key] = func(*args)
    return CACHE[key]
