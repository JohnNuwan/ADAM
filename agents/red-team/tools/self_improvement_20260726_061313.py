# Auto-amélioration de adam-red-team
# Demande: Ajouter un système de retry aux outils
# Date: 2026-07-26T06:13:13.387677
import time
def retry(func, max=3):
    for i in range(max):
        try: return func()
        except: time.sleep(1)
    return None
