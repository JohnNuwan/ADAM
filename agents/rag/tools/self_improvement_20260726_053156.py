# Auto-amélioration de adam-rag
# Demande: Ajouter un système de retry aux outils
# Date: 2026-07-26T05:31:56.006355
import time
def retry(func, max=3):
    for i in range(max):
        try: return func()
        except: time.sleep(1)
    return None
