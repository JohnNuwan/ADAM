# Auto-amélioration de adam-ctf
# Demande: Ajouter un cache aux outils pour éviter les appels dupliqués
# Date: 2026-07-26T04:54:42.862193
CACHE = {}
def cached_call(key, func, *args):
    if key not in CACHE:
        CACHE[key] = func(*args)
    return CACHE[key]
