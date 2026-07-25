#!/usr/bin/env python3
"""
Handler RAG pour l'event bus Adam.
Écoute les channels rag:query, rag:reindex, rag:search.

Délègue au serveur RAG (ChromaDB + HippoRAG 2) via HTTP API.
Le serveur RAG tourne sur http://localhost:8083.
"""
import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone

RAG_URL = os.environ.get("RAG_URL", "http://localhost:8083")
ADAM_V2_DIR = os.environ.get("ADAM_V2_DIR", os.path.expanduser("~/eva-adam-v2"))
sys.path.insert(0, ADAM_V2_DIR)

def heartbeat(agent_id="eva-rag", status="ok", error=None):
    """Publie un heartbeat sur le bus d'événements."""
    try:
        from event_bus import EventBus
        bus = EventBus(db_path=os.path.join(ADAM_V2_DIR, "event_bus.db"))
        bus.update_agent_status(
            agent_id, status,
            last_error=error,
            heartbeat_at=datetime.now(timezone.utc).isoformat(),
        )
    except Exception as e:
        print(f"⚠️ Impossible d'envoyer le heartbeat: {e}", file=sys.stderr)

def handle_query(payload):
    """Traite une requête RAG: interroge le serveur RAG."""
    question = payload.get("question") or payload.get("query") or ""
    if not question:
        return {"error": "Aucune question fournie", "status": "error"}

    try:
        url = f"{RAG_URL}/api/rag/query"
        data = json.dumps({"question": question}).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode("utf-8"))
        print(f"✅ Requête RAG traitée: '{question[:60]}...'")
        print(f"   Sources: {len(result.get('sources', []))}")
        return result
    except urllib.error.URLError as e:
        print(f"⚠️ Serveur RAG indisponible ({RAG_URL}): {e}", file=sys.stderr)
        return {"error": f"Serveur RAG indisponible: {e}", "status": "offline"}
    except Exception as e:
        print(f"❌ Erreur requête RAG: {e}", file=sys.stderr)
        return {"error": str(e), "status": "error"}

def handle_reindex(payload):
    """Déclenche une réindexation RAG."""
    try:
        url = f"{RAG_URL}/api/rag/reindex"
        req = urllib.request.Request(url, data=b"{}", headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=300) as resp:
            result = json.loads(resp.read().decode("utf-8"))
        print(f"✅ Réindexation RAG terminée: {result.get('total_docs', '?')} docs")
        return result
    except urllib.error.URLError as e:
        print(f"⚠️ Serveur RAG indisponible: {e}", file=sys.stderr)
        return {"error": f"Serveur RAG indisponible: {e}", "status": "offline"}
    except Exception as e:
        print(f"❌ Erreur réindexation: {e}", file=sys.stderr)
        return {"error": str(e), "status": "error"}

def main():
    channel = os.environ.get("ADAM_EVENT_CHANNEL", "")
    payload_str = os.environ.get("ADAM_EVENT_PAYLOAD", "{}")
    agent_id = os.environ.get("ADAM_AGENT_ID", "eva-rag")

    print(f"🔄 Handler RAG déclenché sur channel '{channel}'")

    try:
        payload = json.loads(payload_str)
    except json.JSONDecodeError:
        payload = {}

    if channel == "rag:query":
        result = handle_query(payload)
    elif channel == "rag:reindex":
        result = handle_reindex(payload)
    elif channel == "rag:search":
        # Search = query simplifiée
        result = handle_query(payload)
    else:
        print(f"⚠️ Channel non géré: {channel}")
        result = {"error": f"Channel non géré: {channel}", "status": "error"}

    # Heartbeat
    status = "ok" if result.get("status") != "error" else "error"
    heartbeat(agent_id=agent_id, status=status,
              error=result.get("error") if status == "error" else None)

    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if status == "ok" else 1)

if __name__ == "__main__":
    main()
