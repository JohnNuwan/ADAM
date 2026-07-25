#!/usr/bin/env python3
"""Migre les donnes de event_bus.db vers PostgreSQL (knowledge graph)"""
import sqlite3, psycopg2, json, os, time
from datetime import datetime

PG_DSN = os.environ.get("PG_DSN", "postgres://adam:adam_secret_2026@localhost:5432/adam")
SQLITE_PATH = os.environ.get("SQLITE_PATH", "/home/aza/eva-adam-v2/data/event_bus.db")

print(f"Migration de {SQLITE_PATH} vers PostgreSQL...")

# Connexion SQLite
sl = sqlite3.connect(SQLITE_PATH)
sl.row_factory = sqlite3.Row

# Connexion PG
pg = psycopg2.connect(PG_DSN)
pg.autocommit = True
cur = pg.cursor()

# 1. Migrer les events
try:
    rows = sl.execute("SELECT * FROM events LIMIT 10000").fetchall()
    print(f"  {len(rows)} evenements trouves dans SQLite")
    for row in rows:
        try:
            payload = json.loads(row["payload"]) if isinstance(row["payload"], str) else row["payload"]
            meta = json.loads(row["metadata"]) if isinstance(row["metadata"], str) else row["metadata"]
        except:
            payload = {"raw": str(row["payload"])}
            meta = {}
        cur.execute(
            """INSERT INTO events (topic, source, payload, metadata, priority, created_at)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (row["topic"], row["source"], json.dumps(payload), json.dumps(meta),
             row.get("priority", 5), row.get("created_at", datetime.now()))
        )
    print(f"  {len(rows)} evenements migres")
except Exception as e:
    print(f"  Erreur migration events: {e}")

# 2. Creer des nuds knowledge graph a partir des agents
agents = ["praetor", "sentinel", "critic", "scribe", "skillsmith", "doctor",
          "treasurer", "social", "osint", "researcher", "rag", "viz", "ctf",
          "blue-team", "red-team"]
for agent in agents:
    cur.execute(
        """INSERT INTO knowledge_nodes (label, name, properties)
           VALUES ('Agent', %s, %s)
           ON CONFLICT DO NOTHING""",
        (agent, json.dumps({"repo": f"https://github.com/JohnNuwan/ADAM-{agent}", "status": "migrated"}))
    )
print(f"  {len(agents)} agents crees dans knowledge graph")

# 3. Creer les topics comme nuds
topics = set()
try:
    for row in sl.execute("SELECT DISTINCT topic FROM events"):
        topics.add(row["topic"])
    for topic in topics:
        cur.execute(
            "INSERT INTO knowledge_nodes (label, name) VALUES ('Topic', %s) ON CONFLICT DO NOTHING",
            (topic,)
        )
    print(f"  {len(topics)} topics crees")
except:
    pass

# Nettoyage
sl.close()
pg.commit()
cur.close()
pg.close()
print("Migration terminee !")
