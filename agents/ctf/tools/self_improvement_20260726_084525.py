# Auto-amélioration de adam-ctf
# Demande: Ajouter un cache aux outils pour éviter les appels dupliqués
# Date: 2026-07-26T08:45:25.404727
CACHE = {}
def cached_call(key, func, *args):
    if key not in CACHE:
        CACHE[key] = func(*args)
    return CACHE[key]
