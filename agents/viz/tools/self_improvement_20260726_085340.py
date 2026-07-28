# Auto-amélioration de adam-viz
# Demande: Ajouter un cache aux outils pour éviter les appels dupliqués
# Date: 2026-07-26T08:53:40.723187
CACHE = {}
def cached_call(key, func, *args):
    if key not in CACHE:
        CACHE[key] = func(*args)
    return CACHE[key]
