# Auto-amélioration de adam-skillsmith
# Demande: Ajouter un cache aux outils pour éviter les appels dupliqués
# Date: 2026-07-26T03:58:28.896275
CACHE = {}
def cached_call(key, func, *args):
    if key not in CACHE:
        CACHE[key] = func(*args)
    return CACHE[key]
