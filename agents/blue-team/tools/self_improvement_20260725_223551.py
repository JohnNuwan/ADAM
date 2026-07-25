# Auto-amélioration de adam-blue-team
# Demande: Ajouter un système de retry aux outils
# Date: 2026-07-25T22:35:51.708195
import time
def retry(func, max=3):
    for i in range(max):
        try: return func()
        except: time.sleep(1)
    return None
