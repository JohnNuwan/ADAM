# Auto-amélioration de adam-praetor
# Demande: Ajouter un système de retry aux outils
# Date: 2026-07-26T01:43:22.449414
import time
def retry(func, max=3):
    for i in range(max):
        try: return func()
        except: time.sleep(1)
    return None
