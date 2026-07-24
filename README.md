# 🐝 EVA-ADAM v2 — The Hive

> Système multi-agent autonome auto-améliorant pour E.V.A (Evolving Virtual Assistant)
> **The Hive** — 192.168.1.5 · 2×RTX 3090 · 24/7

## 📋 Vue d'ensemble

EVA-ADAM v2 est le système nerveux central de **The Hive**. Il orchestre une collectivité d'agents IA autonomes (« Adams ») qui communiquent via un bus d'événements SQLite, s'auto-réparent via `self_heal.py`, et évoluent via `adam-evolution.py`.

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    EVENT BUS (SQLite WAL)                │
│                   event_bus.db (13 MB)                   │
├─────────────────────────────────────────────────────────┤
│  events │ subscriptions │ agents │ ...                  │
└────┬────┴───────┬───────┴────────┴──────────────────────┘
     │            │
     ▼            ▼
┌─────────┐  ┌───────────┐  ┌──────────────┐
│ Daemons │  │  Handlers  │  │  Self-Heal   │
│         │  │ (scripts/) │  │  (15 min)    │
└─────────┘  └───────────┘  └──────────────┘
```

### Composants principaux

| Fichier | Rôle | Statut |
|---------|------|--------|
| `event_daemon.py` | Bus d'événements (dispatch des handlers) | ✅ Actif |
| `event_bus.py` | API Python pour le bus d'événements | ✅ |
| `self_heal.py` | Auto-réparation des Adams (exit codes 126/127/1/2) | ✅ Cron 15min |
| `adam-evolution.py` | Évolution auto des règles et agents | ✅ Actif |
| `hive_cycler.py` | Cycles de vie de la ruche | ✅ Actif |
| `file_watcher.py` | Surveillance des fichiers → git:changes_detected | ✅ Actif |
| `adam.py` | CLI principal | ✅ |
| `v2_adapter.py` | Adaptateur v1→v2 | ✅ |
| `state_isolation.py` | Isolation d'état entre agents | ✅ |
| `worker_loop.py` | Boucle worker pour tâches longues | ✅ |
| `publish.py` | Publication d'événements | ✅ |
| `heal-handler.sh` | Handler pour self_heal | ✅ |
| `soul.md` | Directives spirituelles d'EVA | ✅ |

### Scripts externes (`~/scripts/`)

| Script | Rôle | Canal(s) |
|--------|------|----------|
| `scribe-write.sh` | Rédaction de contenu, docs, articles | content:request, architecture:proposal, skill:created, skill:updated |
| `docs-handler.sh` | Mise à jour du wiki/docs | wiki:update |
| `skillsmith-create.sh` | **Création auto de skills** | research:opportunity, skill:request |
| `adam-red-challenge.py` | Red Team — escalade root Android | osint:alert, security:challenge |
| `osint-handler.py` | Recherche OSINT | security:scan |
| `cicd-hook.sh` | CI/CD — auto-commit, tests, push | git:changes_detected |
| `kali_bridge.py` | Pont vers le conteneur Kali (42 outils) | — |

## 🤖 Agents (22+)

| Agent | Rôle | Canaux écoutés |
|-------|------|----------------|
| `adam-scribe` | Rédaction de contenu et docs | content:request, architecture:proposal, skill:created, skill:updated |
| `adam-docs` | Documentation wiki | wiki:update |
| `adam-cicd` | CI/CD — auto-commit et push | git:changes_detected, git:auto_fix |
| `adam-critic` | Revue de code | code:review, skill:updated |
| `adam-architect` | Propositions d'architecture | architecture:request |
| `adam-red` | Red Team — pentest Android | osint:alert, security:challenge, security:scan |
| `adam-research` | Recherche scientifique | research:request |
| `adam-osint` | OSINT | osint:request |
| `adam-skillsmith` | **Création auto de skills** | research:opportunity, skill:request |
| `adam-ctf` | Résolution de challenges CTF | ctf:challenge |
| `adam-evolution` | Évolution des règles | evolution:cycle |
| `adam-finance` | Suivi financier | finance:report |
| ... | *(22 agents au total)* | ... |

### Self-Heal

Le `self_heal.py` corrige automatiquement les Adams qui échouent :

| Exit code | Diagnostic | Correction |
|-----------|-----------|------------|
| 126 | Permission denied | `chmod +x` sur le handler |
| 127 | Command not found | `pip install` du module manquant |
| 1 | Erreur Python | `python3 -m py_compile` + diagnostic |
| 2 | Erreur de syntaxe bash | `bash -n` + signalement |

## 📁 Structure du repo

```
eva-adam-v2/
├── README.md            ← Ce fichier
├── adam.py              ← CLI principal
├── event_daemon.py      ← Daemon du bus d'événements
├── event_bus.py         ← API bus d'événements
├── self_heal.py         ← Auto-réparation (58 KB)
├── adam-evolution.py    ← Évolution auto (50 KB)
├── hive_cycler.py       ← Cycles de vie
├── file_watcher.py      ← Surveillance fichiers
├── soul.md              ← Directives EVA
├── event_bus.db         ← SQLite WAL (13 MB)
├── config/              ← Configuration
├── docs/                ← Documentation auto-générée
│   ├── guide_adam_v2.md
│   └── architecture/    ← Propositions d'architecture
├── logs/                ← Logs des handlers
├── reports/             ← Rapports des Adams
│   ├── red-team/        ← Rapports Adam-Red
│   └── research/        ← Rapports Adam-Research
├── scripts/             ← Scripts internes
│   ├── adam-ctf.py
│   ├── kali_bridge.py   ← Pont Kali Docker (502 lignes)
│   └── ...
├── tasks/               ← Tâches auto-générées
├── tools/               ← Outils divers
├── wordlists/           ← Wordlists pour pentest
├── evolution/           ← État de l'évolution
├── fixes/               ← Correctifs auto appliqués
├── ctf/                 ← Challenges CTF résolus
└── social/              ← Médias sociaux
```

## 🛠️ Infrastructure

- **Machine** : The Hive (192.168.1.5), headless, 2×RTX 3090
- **OS** : Debian 13 (Linux 6.12.94)
- **Python** : 3.11.15 (système) + 3.13 (pip)
- **Docker** : Conteneur `kali-pentest` (42 outils de pentest)
- **Dashboards** :
  - `:8081` — Monitoring
  - `:8082` — Wiki D3.js
  - `:8083` — RAG
  - `:8084` — Adam-Viz 3D
- **LLM** : vLLM Mistral 24B `:8000` · Ollama `:11434`

## 📊 Métriques

- **22 agents** enregistrés
- **51+ souscriptions** au bus d'événements
- **42 canaux** actifs
- **1 145 skills** dans `~/.hermes/skills/`
- **10/10 challenges CTF** résolus (100%)
- **14 skills** créés par EVA/Adam

## 🔧 Démarrage

```bash
# Lancer le daemon du bus d'événements
python3 event_daemon.py &

# Lancer le self_heal (cron 15 min)
python3 self_heal.py &

# Lancer le hive_cycler
python3 hive_cycler.py &

# Lancer le file_watcher
python3 file_watcher.py &

# Lancer adam-evolution
python3 adam-evolution.py &
```

## 📝 Licence

Projet privé — **The Hive** — E.V.A (Evolving Virtual Assistant)

---

*Maintenu par EVA et ses Adams. Dernière mise à jour: 2026-07-24*
