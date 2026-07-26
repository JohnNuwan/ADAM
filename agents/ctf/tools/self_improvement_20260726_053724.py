# Auto-amélioration de adam-ctf
# Demande: Ajouter un cache aux outils pour éviter les appels dupliqués
# Date: 2026-07-26T05:37:24.810125
CACHE = {}
def cached_call(key, func, *args):
    if key not in CACHE:
        CACHE[key] = func(*args)
    return CACHE[key]
