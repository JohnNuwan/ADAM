# Auto-amélioration de adam-skillsmith
# Demande: Ajouter un système de retry aux outils
# Date: 2026-07-25T23:00:22.884829
import time
def retry(func, max=3):
    for i in range(max):
        try: return func()
        except: time.sleep(1)
    return None
