# Task: refactor — factorization

- **Fichier:** `/home/aza/eva-adam-v2/adam-evolution.py:812`
- **Sévérité:** info
- **Type:** factorization
- **Date:** 20260723-145714

## Problème

4 fonctions similaires (préfixe '_ch'): _check_duplication(adam-evolution.py:812), _check_gpu(self_heal.py:836), _check_memory(self_heal.py:870), _check_service(self_heal.py:891)

## Suggestion

Considérer une factory ou classe de base pour '_ch...'

## Action requise

Corriger quand possible
