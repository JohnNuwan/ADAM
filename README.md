# 🐝 ADAM — Framework Multi-Agent Autonome

> Système nerveux central de **The Hive**
> 192.168.1.5 · 2×RTX 3090 · 32 cœurs · 126Go RAM

## 🚀 Démarrage rapide

```bash
# Cloner
git clone git@github.com:JohnNuwan/ADAM.git
cd ADAM/docker

# Lancer toute la stack
docker compose up -d

# Vérifier
docker compose ps
curl http://localhost:8086/api/health
```

## 🏗️ Architecture

```
                    ┌─────────────────────┐
                    │   Go Event Bus       │  ← Système nerveux temps réel
                    │   (HTTP + WebSocket) │     port 8086
                    └──────┬──────────────┘
                           │
    ┌──────────────────────┼──────────────────────┐
    │                      │                      │
  Agent Viz            Agent Chat             Scripts ADAM
  (port 8084)          (port 8085)            (Go Bus Client)
    │                      │                      │
    └──────────────────────┼──────────────────────┘
                           │
                    ┌──────┴──────────────┐
                    │    PostgreSQL 17      │  ← Mémoire longue durée
                    │  + PGVector (RAG)     │     port 5432
                    │  + Knowledge Graph    │
                    └─────────────────────┘
                           │
                    ┌──────┴──────────────┐
                    │  Graphify 3D (8090)  │  ← Knowledge Graph 3D
                    └─────────────────────┘
```

## 📦 Composants Docker

| Service | Port | Technologie | Rôle |
|---------|------|-------------|------|
| `postgres` | 5432 | PostgreSQL 17 + PGVector | Base de données + RAG + Graph |
| `go-bus` | 8086 | Go 1.23 | **Event Bus** temps réel (système nerveux) |
| `adam-viz` | 8084 | Python + Three.js | Dashboard temps réel 3D |
| `adam-chat` | 8085 | Python + Flask-SocketIO | Messagerie chiffrée AES-256 |
| `graphify` | 8090 | Python + Three.js | Visualisation Knowledge Graph 3D |

## 🧠 Agents ADAM

Voir [agents.yaml](agents.yaml) pour le registre complet.

## 🔒 Pipeline de vérification (ADAM-GATE)

Avant chaque commit, 4 vérificateurs s'assurent de la qualité et de la sécurité :

- **Adam-Critic** : syntaxe Python, TODO, print()
- **Adam-Praetor** : tokens, mots de passe, IP exposées
- **Adam-Sentinel** : dépendances, versions pinées
- **Adam-Doctor** : conflits de merge, fichiers orphelins

```bash
git commit  # ← ADAM-GATE se lance automatiquement
# En cas d'urgence :
git commit --no-verify -m "message"
```

## 🔄 Synchronisation automatique

Un cron (2h et 14h) SSH dans TheHive et exécute :
```bash
cd /home/aza/eva-adam-v2
bash scripts/git-sync.sh  # git pull → commit → push
```

## 📁 Structure du dépôt

```
ADAM/
├── core/              ← Moteur central
├── agents/            ← 15 agents spécialisés
├── scripts/           ← git-sync, adam-gate, deploy
├── data/              ← Bases de données (gitignoré)
├── docker/            ← Docker Compose + Go Bus + services
│   ├── docker-compose.yml
│   ├── bus/           ← Go Event Bus (code source)
│   ├── postgres/      ← Init SQL + extensions
│   ├── agents/        ← Dockerfiles viz, chat
│   └── graphify_server.py
├── agents.yaml        ← Registre des agents
├── pyproject.toml
├── ARCHITECTURE.md
└── README.md
```

## 🚢 Déploiement ailleurs

```bash
git clone git@github.com:JohnNuwan/ADAM.git
cd ADAM/docker
docker compose up -d
# Stack complète opérationnelle en 30 secondes
```

## 📊 Stats serveur (TheHive)

- **GPU** : 2× RTX 3090 (vLLM Qwen2.5-32B-AWQ + ComfyUI)
- **Disque** : root 65%, /mnt/data 43%
- **RAM** : 126 Go (11 Go utilisé, 113 Go libre)
- **Uptime** : variable (auto-heal)
