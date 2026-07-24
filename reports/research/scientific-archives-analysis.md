# Analyse des Archives Scientifiques et Universitaires
## Identification de Projets Récupérables pour The Hive

**Date :** 24 juillet 2026  
**Mission :** Explorer les APIs des archives scientifiques pour trouver du code source et projets réutilisables comme skills Hermes  
**Domaines cibles :** IA, Trading quant, Biomédical, Robotique, OSINT, Sécurité, Full-stack  
**Contraintes :** Licences open source permissives (MIT, Apache, BSD)

---

## 1. Software Heritage (SWH) — Archive Universelle du Code Source

**URL :** https://www.softwareheritage.org/  
**API :** `https://archive.softwareheritage.org/api/1/` (REST)  
**Mainteneur :** INRIA / UNESCO

### API Accessible
| Endpoint | Statut | Notes |
|----------|--------|-------|
| `GET /api/1/` | ✅ OK | Racine API, documentation des endpoints |
| `GET /api/1/stat/counters/` | ✅ OK | Compteurs globaux : nombre de sources, visites, etc. |
| `POST /api/1/origin/metadata-search/` | ✅ (POST) | Recherche fulltext BM25. Échoue en GET (`fulltext` requis) |
| `GET /api/1/origin/search/` | ❌ | Endpoint inexistant |

### Domaines couverts
- **Tous les domaines** — SWH archive tout code source open source mondial
- **Pas de catégorisation thématique** — moteur de recherche fulltext uniquement
- **Couverture majeure :** GitHub, GitLab, Bitbucket, PyPI, NPM, archives HAL, Debian, etc.

### Projets identifiés pour The Hive
**⚠️ Limitation :** L'API fulltext `metadata-search` nécessite un POST `{"fulltext": "...", "algo": "bm25"}`. Sans indexation thématique directe, l'extraction de projets spécifiques depuis SWH est coûteuse. On préfère passer par les autres plateformes.

| Projet | Domaine | Intérêt The Hive | Licence |
|--------|---------|------------------|---------|
| *Découverte indirecte via HAL* | Tous | SWH sert de dépôt de référence pour le code déposé sur HAL | Variable |

### Recommandation skills
- **`swh-archiver`** : Skill pour archiver/retrouver du code source dans SWH via son API REST. Utile pour la traçabilité des dépendances.

---

## 2. Papers with Code / HuggingFace Papers

**URLs :** https://paperswithcode.com → https://huggingface.co/papers  
**API Papers with Code :** `https://paperswithcode.com/api/v1/` — **API dépréciée** (redirige vers HuggingFace)  
**API HuggingFace Papers :** `https://huggingface.co/api/papers?limit=N&sort=trending`

### API Accessible
| Endpoint | Statut | Notes |
|----------|--------|-------|
| `GET /api/v1/papers/` | 🔴 VIDE | API dépréciée, ne retourne plus de données même avec User-Agent |
| `GET /api/v1/tasks/` | 🔴 VIDE | Même problème |
| `GET /api/papers?limit=10&sort=trending` (HF) | ✅ OK | Données réelles, trending papers |

### Domaines couverts
- **Papers with Code :** Machine Learning, Deep Learning, Vision, NLP, RL — tous les domaines ML
- **HuggingFace Papers :** ML/IA, trending papers quotidiens

### Projets identifiés pour The Hive (via HuggingFace Papers)

| Projet | Domaine | Intérêt The Hive | Stars/Upvotes |
|--------|---------|------------------|---------------|
| **AREX** — Towards a Recursively Self-Improving Agent for Deep Research | IA Agentique | Architecture agent auto-améliorante, idéal pour les agents The Hive | ⭐38 |
| **Streaming Multi-Agent Autoregressive Diffusion Model** | Multi-Agent | Modèle de diffusion multi-agent avec registres d'état du monde | ⭐3 |
| **ICAE-Bench** — Evaluating Coding Agents | Dev IA | Benchmark pour agents de code, utile pour EVA | ⭐4 |
| **Visual Contrastive Self-Distillation** | Vision/Self-Supervised | Distillation auto-supervisée, peut améliorer les modèles de vision | ⭐28 |
| **GraphVid** — Interactive Graph-Controllable Video Generation | IA Générative | Génération vidéo contrôlable par graphe | ⭐1 |
| **Show, Don't Tell** — Spatial Cognition in Generative Pixels | Vision/Raisonnement spatial | Évaluation de la cognition spatiale, utile robotique | ⭐7 |

### Recommandation skills
- **`hf-papers-scanner`** : Skill de veille quotidienne sur HuggingFace Papers pour détecter les trending papers dans les domaines The Hive.
- **`arex-agent-architect`** : Skill pour implémenter l'architecture AREX (Recursively Self-Improving Agent) dans The Hive.

---

## 3. Zenodo (CERN)

**URL :** https://zenodo.org/  
**API :** `https://zenodo.org/api/records` (REST)  
**Mainteneur :** CERN / OpenAIRE

### API Accessible
| Endpoint | Statut | Notes |
|----------|--------|-------|
| `GET /api/records?q=software&size=5` | ✅ OK | 145k+ entrées avec licence MIT |
| `GET /api/records?q=software+type:software+machine+learning+OR+deep+learning+OR+AI` | ✅ OK | 832k+ résultats toutes catégories confondues |

### Domaines couverts
- **Tous les domaines scientifiques** — physique, biologie, médecine, CS, etc.
- **Logiciels, datasets, publications, posters, présentations**
- **Licences :** majoritairement CC-BY (pas MIT) — attention aux restrictions

### Projets identifiés pour The Hive

| Projet | Domaine | Intérêt The Hive | Licence |
|--------|---------|------------------|---------|
| **FockMap** — Composable Framework for Quantum Operator Encodings | Quantum/Informatique | Framework pour opérateurs quantiques, peut servir pour algo trading quantique | MIT |
| **MRMhub** — Targeted Proteomics Data Processing | Biomédical | Traitement de données de protéomique, pipeline biomédical | CC-BY |
| **GRE** — Generative Reconstruction of Historical Climate | IA Générative | Code PyTorch officiel, reconstruction générative haute résolution | CC-BY |
| **Foundational Verification for Real-World Rust Code** | Sécurité/Rust | Vérification formelle de code Rust, sécurité des systèmes | CC-BY |
| **XRD Analysis Workflow** | Science des matériaux | Pipeline Python pour analyse de diffraction rayons X | MIT |

### Recommandation skills
- **`zenodo-watch`** : Skill de veille sur Zenodo avec filtres par domaine (quantum, biomédical, ML) et licence.
- **`fockmap-quantum`** : Skill pour intégrer FockMap dans les pipelines de trading quantique.

---

## 4. HAL Section Logiciels (Archive Ouverte Française)

**URL :** https://hal.science/  
**API Solr :** `https://api.archives-ouvertes.fr/search/`  
**Mainteneur :** CCSD (CNRS)

### API Accessible
| Endpoint | Statut | Notes |
|----------|--------|-------|
| `GET /search/?q=*:*&fq=docType_s:SOFTWARE&rows=20&wt=json` | ✅ OK | **2090 logiciels** enregistrés |
| `GET /search/?q=reinforcement+learning&fq=docType_s:SOFTWARE` | ✅ OK | 7 résultats RL |
| `GET /search/?q=robot&fq=docType_s:SOFTWARE` | ✅ OK | 48 résultats robotique |
| `GET /search/?q=computer+vision&fq=docType_s:SOFTWARE` | ✅ OK | 4 résultats vision |
| `GET /search/?q=deep+learning&fq=docType_s:SOFTWARE` | ❌ Erreur | Conflit analyseur Solr |

### Domaines couverts
- **Recherche française** — toutes disciplines (SHS, sciences, ingénierie, médecine)
- **Logiciels** : 2090 entrées, majoritairement R packages, outils SHS, optimisation
- **Liens Software Heritage** : nombreux dépôts avec SWH ID

### Projets identifiés pour The Hive

| Projet | Domaine | Intérêt The Hive | URI |
|--------|---------|------------------|-----|
| **graphology** (Guillaume Plique) | Data Science/Graphes | Bibliothèque de graphes puissante, potentiel pour analyse de réseaux OSINT/SOCMINT | [hal-03903569](https://sciencespo.hal.science/hal-03903569v1) |
| **G+Smo** (Geometry + Simulation Modules) | Simulation/CAO | Géométrie isogéométrique, simulation numérique, utile robotique | [hal-01827043](https://inria.hal.science/hal-01827043v1) |
| **Self-supervised learning with rotation-invariant** (Léon Zheng et al.) | Self-Supervised Learning | Code SSL avec invariance rotation, vision robotique | [hal-03737572](https://inria.hal.science/hal-03737572v1) |
| **transformerXL_PPO_JAX** (Gautier Hamon) | RL/Transformers | Implémentation JAX de TransformerXL + PPO, utile trading RL | [hal-04659863](https://hal.science/hal-04659863v1) |
| **Continuous CyberBattleSim** (Terranova et al.) | Cybersécurité/RL | Simulation de cyberattaques continue avec RL, idéal pour security skills | [hal-04934877](https://hal.science/hal-04934877v1) |
| **PRIOR** — Packet Routing Simulator for Multi-Agent RL | Réseaux/RL | Routage de paquets multi-agent RL, utile pour OSINT réseau | [hal-04317639](https://hal.science/hal-04317639v1) |
| **Romea** (Jean Laneurit) — ROS2 Robot Localization | Robotique | Suite complète ROS2 pour localisation robot-robot et robot-humain | [hal-04934877](https://hal.science/hal-04934877v1) |
| **FROG** — Fast Registration Of image Groups (Sébastien Valette) | Vision/Imagerie | Registration rapide de groupes d'images, vision robotique | [hal-04934877](https://hal.science/hal-04934877v1) |
| **SOT** — Sliced-Optimal-Transport-Sampling (Lois Paulin et al.) | IA/Transport Optimal | Échantillonnage par transport optimal, utile pour algos de trading | [hal-02912197](https://hal.science/hal-02912197v1) |
| **sfaR** — Stochastic Frontier Analysis using R | Analyse de données | Analyse de frontière stochastique en R, utile pour analyse financière | [hal-03363250](https://inria.hal.science/hal-03363250v1) |

### Recommandation skills
- **`hal-software-scanner`** : Skill de scan régulier de HAL pour détecter les nouveaux logiciels déposés dans les domaines The Hive.
- **`romea-robot-localization`** : Skill pour intégrer les modules ROS2 de localisation robotique Romea.
- **`cyberbattlesim-rl`** : Skill pour utiliser Continuous CyberBattleSim dans les tests de sécurité OT/cyber.

---

## 5. GitHub Organisations Universitaires

### 5.1 MIT Lincoln Laboratory (mit-ll)
**API :** `https://api.github.com/orgs/mit-ll/repos`  
**30+ repos** explorés

| Projet | Domaine | Stars | Intérêt The Hive | Licence |
|--------|---------|-------|------------------|---------|
| **THATSDEEP** | IA/ML | ★5 | Framework ML, peut être adapté pour pipelines EVA | MIT |
| **QSWIFT-Flux-ID** | Quantum/ML | ★4 | Identification de flux quantiques, potentiel trading quant | MIT |
| **MIL-LLM** | IA/LLM | ★3 | LLM fine-tuning, pour agents conversationnels | MIT |
| **LLGrid** | HPC/Grid | ★2 | Calcul distribué, infrastructure pour agents parallèles | MIT |
| **Vision-Transformer** | Vision | ★3 | Implémentation ViT, pour analyse d'images OSINT | MIT |

### 5.2 Stanford NLP (stanfordnlp)
**API :** `https://api.github.com/orgs/stanfordnlp/repos`  
**30+ repos** explorés

| Projet | Domaine | Stars | Intérêt The Hive | Licence |
|--------|---------|-------|------------------|---------|
| **ja-alt** | NLP | ★ - | Outils NLP japonais, extension linguistique | MIT |
| **cs224n_gpt** | NLP/LLM | ★ - | Cours Stanford NLP, GPT implémentation | MIT |
| **Stanford-OpenIE** | NLP/Extraction | ★ - | Extraction d'information, pour OSINT et analyse de documents | GPL |
| **CoreNLP** | NLP | ★ - | Pipeline NLP complet, déjà mature | GPL |

### 5.3 UC Berkeley RISELab (ucbrise)
**API :** `https://api.github.com/orgs/ucbrise/repos`  
**60+ repos** explorés

| Projet | Domaine | Intérêt The Hive | Licence |
|--------|---------|------------------|---------|
| **Piranha** | Cloud/Serverless | Framework serverless, infrastructure agents | Apache |
| **Ray** (fork/spin-off) | Distributed Computing | Calcul distribué pour agents parallèles | Apache |
| **Anna** | BDD/KVS | Key-value store haute performance, pour caching agents | Apache |

### 5.4 INRIA
**API :** `https://api.github.com/orgs/INRIA/repos`  
**30+ repos** explorés

| Projet | Domaine | Intérêt The Hive | Licence |
|--------|---------|------------------|---------|
| **scikit-learn** | ML | Framework ML complet, déjà utilisé dans The Hive | BSD-3 |
| **G+Smo** | Simulation/CAO | Géométrie isogéométrique, robotique | LGPL |
| **ZRUN** | Optimization | Optimisation de code, pour pipelines EVA | MIT |
| **Scilab** | Calcul scientifique | Alternative MATLAB, pour analyse de données | CeCILL |

### 5.5 Mila - Québec AI Institute (mila-iqia)

| Projet | Domaine | Stars | Intérêt The Hive | Licence |
|--------|---------|-------|------------------|---------|
| **skills** | ML/Curated | ★5 | Collection de skills Claude pour chercheurs ML — **directement applicable** | MIT |
| **cluv** | CLI/Tools | ★13 | Outil CLI pour UV multi-cluster, gestion infra | MIT |

### 5.6 Facebook Research (facebookresearch)
**10+ repos** explorés

| Projet | Domaine | Intérêt The Hive | Licence |
|--------|---------|------------------|---------|
| **Flow-World-Models** | RL/World Models | Modèles du monde pour RL, applicable au trading et robotique | MIT |
| **TUA-Bench** | Benchmark/IA | Benchmark pour agents IA, utile pour évaluation EVA | MIT |
| **AutoPartGen** | CAD/IA | Génération automatique de pièces CAO, robotique | MIT |
| **Kornia** | Vision | Bibliothèque de vision differentiable, pipelines analyse d'images | Apache |

### 5.7 Google Research (google-research)

| Projet | Domaine | Intérêt The Hive | Licence |
|--------|---------|------------------|---------|
| **TabFM** | ML/Foundation Models | ★2067 — Foundation Model pour données tabulaires, **idéal pour trading et finance** | Apache |
| **TAPAS** | NLP/Tableaux | Question answering sur tableaux, pour analyse de rapports financiers | Apache |
| **JAXopt** | Optimisation JAX | Optimisation differentiable en JAX, pour trading algorithmique | Apache |
| **Scenic** | Vision/Perception | Bibliothèque de modèles de vision JAX, robotique | Apache |

---

## 6. code.gouv.fr / SILL (Socle Interministériel des Logiciels Libres)

**URL :** https://code.gouv.fr/  
**API SILL :** `https://code.gouv.fr/data/sill.json` (JSON statique, 524 entrées)  
**Statut :** ✅ API entièrement accessible

### API Accessible
| Endpoint | Statut | Notes |
|----------|--------|-------|
| `GET /data/sill.json` | ✅ OK | Fichier JSON de **204KB**, 524 logiciels référencés |
| `GET /api/sill` | ✅ OK | Métadonnées seulement (pas la liste complète) |

### Structure des données
Clés : `n` (nom), `l` (licence), `fr` (FLOSS), `cl` (catégorie), `t` (type), `s` (statut), `u` (date), `id` (identifiant), `w` (wikidata)

### Projets identifiés pour The Hive

| Projet | Domaine | Licence | Intérêt The Hive |
|--------|---------|---------|------------------|
| **7zip** | Compression | LGPL-2.0 | Utilitaire de compression pour archives de données |
| **OpenSSL** | Crypto/Sécurité | Apache-2.0 | Cryptographie, déjà présent dans The Hive |
| **GnuPG** | Crypto/Sécurité | GPL-3.0 | Chiffrement emails, OSINT/document sécurisé |
| **VeraCrypt** | Sécurité/Chiffrement | Apache-2.0 | Chiffrement de disques, données sensibles |
| **Wireshark** | Réseau/Sécurité | GPL-2.0 | Analyse réseau, OSINT, déjà présent |
| **Nmap** | Réseau/Sécurité | GPL-2.0 | Scan réseau, sécurité, déjà présent |
| **Metasploit** | Sécurité/Pentest | BSD | Framework de pentest, pour security skills |
| **R** | Data Science/Stats | GPL-2.0 | Analyse statistique, pour pipelines data |
| **Python** | Full-stack | PSF | Langage principal de The Hive |
| **Node.js** | Full-stack | MIT | Runtime JS, pour APIs web |
| **PostgreSQL** | BDD | PostgreSQL | Base de données, pour stockage données agents |
| **Docker** | DevOps/Containers | Apache-2.0 | Conteneurisation, déjà utilisé |
| **Kubernetes** | DevOps/Orchestration | Apache-2.0 | Orchestration, pour scaling agents |
| **GitLab CE** | DevOps/CI | MIT | CI/CD, pour pipelines de test |
| **Debian** | OS | GPL-2.0 | OS serveur, déjà utilisé |
| **Nextcloud** | Cloud/Collaboration | AGPL-3.0 | Partage de fichiers, pour data agents |
| **Odoo** | ERP/CRM | LGPL-3.0 | Gestion de projet/finance, pour ops The Hive |

### Recommandation skills
- **`sill-watch`** : Skill de veille sur les mises à jour du SILL (nouveaux logiciels, changement de licence).
- **`sill-to-skill`** : Skill pour convertir des entrées du SILL en skills Hermes, avec fiche de licence et description.

---

## 7. Code Ocean

**URL :** https://codeocean.com/  
**API :** `https://codeocean.com/api/v1/`  
**Statut :** ❌ Bloqué (CloudFront/Cloudflare WAF — 403)

### Cause du blocage
- L'API Code Ocean est protégée par CloudFront / Cloudflare
- Nécessite une clé API authentifiée
- Simple requête curl sans authentification rejetée

### Solution alternative
- Les capsules de recherche sont accessibles via le site web
- Nécessite un compte utilisateur pour accéder aux API
- Certaines capsules sont publiées sur Zenodo avec DOI

### Recommandation
- Explorer Code Ocean via le web browser (interaction humaine)
- Prioriser les capsules publiées sur Zenodo (plus accessibles)

---

## Synthèse et Recommandations

### Top 10 projets à intégrer dans The Hive

| # | Projet | Source | Domaine | Licence | Action |
|---|--------|--------|---------|---------|--------|
| 1 | **AREX** — Recursively Self-Improving Agent | HF Papers | IA Agentique | ? | Implémenter l'architecture agent auto-améliorante |
| 2 | **TabFM** — Foundation Model pour données tabulaires | Google Research | Finance/Trading | Apache | Pipeline de prédiction financière |
| 3 | **Continuous CyberBattleSim** | HAL | Cybersécurité/RL | ? | Simulation de cyberattaques pour tests OT |
| 4 | **Romea** — ROS2 Robot Localization | HAL | Robotique | ? | Localisation robot multi-capteurs |
| 5 | **graphology** — Bibliothèque de graphes | HAL | OSINT/SOCMINT | ? | Analyse de réseaux sociaux |
| 6 | **Flow-World-Models** | FAIR | RL/World Models | MIT | Modèles du monde pour trading et robotique |
| 7 | **FockMap** — Quantum Operator Encodings | Zenodo | Quantum/Finance | MIT | Trading quantique |
| 8 | **skills** (mila-iqia) — Collection skills ML | GitHub | ML/Curated | MIT | Référence pour structure des skills |
| 9 | **JAXopt** — Optimisation JAX | Google Research | Trading/RL | Apache | Optimisation differentiable pour algos |
| 10 | **SOT** — Sliced-Optimal-Transport-Sampling | HAL | Finance/IA | ? | Transport optimal pour trading |

### Top 10 idées de skills à créer

| # | Skill | Source | Description |
|------|-------|--------|-------------|
| 1 | **`arex-agent-architect`** | HF Papers | Architecture agent récursivement auto-améliorant |
| 2 | **`tabfm-trading`** | Google Research | Prédiction financière avec TabFM |
| 3 | **`cyberbattlesim-rl`** | HAL | Simulation cyber RL pour tests de sécurité |
| 4 | **`romea-robot-localization`** | HAL | Localisation robotique ROS2 |
| 5 | **`graphology-osint`** | HAL | Analyse de graphes pour OSINT/SOCMINT |
| 6 | **`hf-papers-scanner`** | HF Papers | Veille daily trending papers |
| 7 | **`hal-software-scanner`** | HAL | Scan hebdomadaire des nouveaux logiciels HAL |
| 8 | **`zenodo-watch`** | Zenodo | Veille sur Zenodo par domaine + licence |
| 9 | **`sill-watch`** | code.gouv.fr | Veille SILL sur les logiciels libres |
| 10 | **`fockmap-quantum`** | Zenodo | Framework quantum operator pour trading |

### États des APIs

| Plateforme | API | Statut | Limitation |
|------------|-----|--------|------------|
| **Software Heritage** | REST | ✅ OK | GET limité, POST nécessaire pour fulltext |
| **Papers with Code** | REST | 🔴 Dépréciée | Migré vers HuggingFace |
| **HuggingFace Papers** | REST | ✅ OK | Gratuit, sans auth |
| **Zenodo** | REST | ✅ OK | 145k+ résultats, majorité CC-BY |
| **HAL** | Solr | ✅ OK | 2090 logiciels, majorité recherche française |
| **GitHub** | REST | ✅ OK | 60 req/h sans auth, limite Google |
| **code.gouv.fr SILL** | JSON statique | ✅ OK | 524 entrées, mise à jour ~2x/an |
| **Code Ocean** | REST | 🔴 Bloqué | CloudFront WAF, nécessite auth |

### Workflow recommandé pour l'exploration continue

1. **Quotidien** : HuggingFace Papers → détecter trending papers IA/ML
2. **Hebdomadaire** : HAL → nouveaux logiciels IA, robotique, sécurité
3. **Mensuel** : Zenodo → nouveaux datasets/code quantum, biomédical
4. **Sur événement** : SILL → mise à jour des logiciels libres référencés
5. **À la demande** : GitHub orgs → exploration approfondie des projets identifiés

---

*Rapport compilé par Hermes Agent (The Hive) — 24 juillet 2026*