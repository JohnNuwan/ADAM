#!/usr/bin/env python3
"""ADAM Bus Client — envoie des evenements au Go Event Bus via HTTP"""
import json, os, requests, time

BUS_URL = os.environ.get("BUS_URL", "http://localhost:8086")

def publish(topic, source, payload, priority=5, metadata=None):
    """Publie un evenement sur le bus"""
    msg = {
        "topic": topic,
        "source": source,
        "payload": payload,
        "priority": priority,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }
    if metadata:
        msg["metadata"] = metadata
    try:
        r = requests.post(f"{BUS_URL}/api/publish", json=msg, timeout=5)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"[BUS] Erreur publish: {e}")
        return None

def query(topic, limit=100):
    """Recupere l'historique des evenements"""
    try:
        r = requests.get(f"{BUS_URL}/api/query", params={"topic": topic, "limit": limit}, timeout=5)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"[BUS] Erreur query: {e}")
        return []

def stats():
    """Recupere les stats du bus"""
    try:
        r = requests.get(f"{BUS_URL}/api/stats", timeout=5)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"[BUS] Erreur stats: {e}")
        return {}

if __name__ == "__main__":
    # Test
    r = publish("adam:test", "bus-client", {"msg": "Client Python OK"})
    print("Publish:", r)
    print("Stats:", stats())
