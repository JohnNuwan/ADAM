#!/usr/bin/env python3
"""
publish.py — CLI pour que les handlers ADAM publient de nouveaux events sur le bus.

Usage:
    python3 publish.py <channel> '<json_payload>' [--source <agent_id>]
    
Exemple:
    python3 publish.py security:alert '{"threat":"permission_drift","severity":"low"}' --source adam-blue
"""
import sys
import os
import json
from pathlib import Path

V2_DIR = Path(__file__).parent
sys.path.insert(0, str(V2_DIR))

from event_bus import EventBus

def main():
    if len(sys.argv) < 3:
        print("Usage: publish.py <channel> '<json_payload>' [--source <agent_id>]", file=sys.stderr)
        sys.exit(1)
    
    channel = sys.argv[1]
    payload_str = sys.argv[2]
    source = "handler"
    
    # Parse --source
    if "--source" in sys.argv:
        idx = sys.argv.index("--source")
        if idx + 1 < len(sys.argv):
            source = sys.argv[idx + 1]
    
    # Utilise ADAM_AGENT_ID si disponible
    agent_id = os.environ.get("ADAM_AGENT_ID", source)
    source = agent_id if source == "handler" else source
    
    try:
        payload = json.loads(payload_str)
    except json.JSONDecodeError:
        payload = {"raw": payload_str}
    
    bus = EventBus()
    event_id = bus.publish(channel, payload, source=source)
    print(f"Published: #{event_id} channel={channel} source={source}")
    bus.close()

if __name__ == "__main__":
    main()
