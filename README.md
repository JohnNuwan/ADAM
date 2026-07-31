# EVA-ADAM v2

Cœur du système ADAM v2 — bus d'événements, orchestration des agents et pipeline de trading automatisé.

## Composants

- **Event Bus**: Système de messagerie asynchrone (Go) pour la communication inter-agents
- **Orchestrateur**: Coordination des cycles de trading, décisions et exécution
- **Agents**: Agents spécialisés (analyse, décision, exécution, surveillance)
- **Self-Heal**: Mécanismes d'auto-guérison et de reprise après incident

## Objectif

Fournir une infrastructure robuste et scalable pour le trading algorithmique multi-agents avec des garanties de résilience.
