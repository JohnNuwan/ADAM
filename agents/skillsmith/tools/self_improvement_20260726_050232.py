# Auto-amélioration de adam-skillsmith
# Demande: Ajouter un système de retry aux outils
# Date: 2026-07-26T05:02:32.674180
import time
def retry(func, max=3):
    for i in range(max):
        try: return func()
        except: time.sleep(1)
    return None
