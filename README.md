# 🐝 ADAM — Framework Multi-Agent Autonome (v2026)

## 📌 Présentation
ADAM est le réseau de 22 agents spécialisés au service de l'entité **EVA**.

## 🏗️ Architecture & Inférence High-Speed
- **Inférence vLLM Dual-Service :**
  - **Code & Workers :** **Codestral-22B** sur le port 8001 (vLLM Tensor Parallelism sur 2× RTX 3090).
  - **Raisonnement Stratégique :** **DeepSeek-R1-Distill** sur le port 8000.
- **Noyau réseau :** Intégration directe avec le bus gRPC Rust/Go (eva-adam-next).
- **Mémoire & Vector Search :** Connecté à la base PostgreSQL + pgvector.
- **Self-Evolution & Healing :** Système de mesure de fitness (evolution/fitness.json) et auto-patching des agents via Praetor et Critic.