# 🐳 ADAM — Stack Docker

## Services

```bash
docker compose up -d          # Lancer tout
docker compose logs -f        # Voir les logs
docker compose ps             # Status des conteneurs
docker compose down           # Arrêter tout
```

## Ports

| Port | Service | Description |
|------|---------|-------------|
| 5432 | PostgreSQL | Base de données (PGVector) |
| 8086 | Go Bus | API HTTP + WebSocket |
| 8084 | ADAM-Viz | Dashboard 3D |
| 8085 | ADAM-Chat | Messagerie chiffrée |
| 8090 | Graphify | Knowledge Graph 3D |

## Go Event Bus API

```bash
# Publier un événement
curl -X POST http://localhost:8086/api/publish \
  -H 'Content-Type: application/json' \
  -d '{"topic":"adam:hello","source":"mon-agent","payload":{"msg":"Hello!"}}'

# Voir les stats
curl http://localhost:8086/api/stats

# Requêter l'historique
curl "http://localhost:8086/api/query?topic=adam:hello&limit=10"

# WebSocket (JavaScript)
const ws = new WebSocket("ws://localhost:8086/ws");
ws.onopen = () => ws.send(JSON.stringify({action:"subscribe",topic:"adam:*"}));
```

## Bases de données PostgreSQL

```bash
docker compose exec postgres psql -U adam -d adam
```

Tables : `events`, `subscriptions`, `knowledge_nodes`, `knowledge_edges`, `documents`, `agents`, `audit_log`

## Migration depuis SQLite

```bash
# Dans le conteneur go-bus :
docker compose cp migrate_sqlite_to_pg.py go-bus:/migrate.py
docker compose exec go-bus python3 /migrate.py
```
