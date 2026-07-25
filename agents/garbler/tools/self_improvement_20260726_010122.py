# Auto-amélioration de adam-garbler
# Demande: Ajouter un cache aux outils pour éviter les appels dupliqués
# Date: 2026-07-26T01:01:22.484709
CACHE = {}
def cached_call(key, func, *args):
    if key not in CACHE:
        CACHE[key] = func(*args)
    return CACHE[key]
