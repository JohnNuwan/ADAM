# Auto-amélioration de adam-praetor
# Demande: Ajouter un cache aux outils pour éviter les appels dupliqués
# Date: 2026-07-26T04:55:37.124580
CACHE = {}
def cached_call(key, func, *args):
    if key not in CACHE:
        CACHE[key] = func(*args)
    return CACHE[key]
