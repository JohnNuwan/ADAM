# Auto-amélioration de adam-doctor
# Demande: Ajouter un cache aux outils pour éviter les appels dupliqués
# Date: 2026-07-26T05:02:51.969745
CACHE = {}
def cached_call(key, func, *args):
    if key not in CACHE:
        CACHE[key] = func(*args)
    return CACHE[key]
