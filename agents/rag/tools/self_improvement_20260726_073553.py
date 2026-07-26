# Auto-amélioration de adam-rag
# Demande: Ajouter un système de retry aux outils
# Date: 2026-07-26T07:35:53.018130
import time
def retry(func, max=3):
    for i in range(max):
        try: return func()
        except: time.sleep(1)
    return None
