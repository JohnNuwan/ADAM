# ADAM — Architecture Framework Multi-Agent

## Structure des répertoires

```
eva-adam-v2/
├── core/                # Moteur central
│   ├── adam.py          # Agent Adam principal
│   ├── adam-evolution.py # Boucle d'auto-évolution
│   ├── event_bus.py     # Bus d'événements SQLite
│   ├── event_daemon.py  # Démon événements
│   ├── file_watcher.py  # Watcher fichiers
│   ├── self_heal.py     # Auto-guérison
│   ├── v2_adapter.py    # Adaptateur v2
│   └── worker_loop.py   # Boucle worker
│
├── agents/              # Agents spécialisés (un dossier par agent)
│   ├── praetor/         # Auto-correction serveurs
│   ├── sentinel/        # Veille & monitoring
│   ├── critic/          # Qualité & review
│   ├── scribe/          # Documentation & écriture
│   ├── skillsmith/      # Création SKILL.md
│   ├── doctor/          # Diagnostic & guérison
│   ├── treasurer/       # Finance
│   ├── social/          # Réseaux sociaux
│   ├── osint/           # OSINT & reconnaissance
│   ├── researcher/      # Scan vulnérabilités
│   ├── rag/             # RAG & connaissances
│   ├── viz/             # Visualisation 3D
│   ├── ctf/             # Challenges CTF
│   ├── blue-team/       # Hardening & défense
│   └── red-team/        # Pentest & Kali
│
├── scripts/             # Scripts utilitaires
├── config/              # Configuration
├── data/                # Bases de données, cache (gitignoré)
│   ├── event_bus.db     # Base événements
│   └── hash_cache/      # Cache de hash
├── docs/                # Documentation
├── evolution/           # Modules d'évolution
├── fixes/               # Correctifs appliqués
├── agents.yaml          # Registre central des agents
├── README.md
└── .gitignore
```

## Workflow Git

1. `git pull origin main` avant toute modif
2. `git add -A` + `git commit -m "message"`
3. `git push origin main`

## Agents actifs

Voir [agents.yaml](agents.yaml) pour la liste complète.

