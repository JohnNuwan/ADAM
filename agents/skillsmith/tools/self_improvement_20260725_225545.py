# Auto-amélioration de adam-skillsmith
# Demande: Ajouter un système de retry aux outils
# Date: 2026-07-25T22:55:45.825139
import time
def retry(func, max=3):
    for i in range(max):
        try: return func()
        except: time.sleep(1)
    return None
