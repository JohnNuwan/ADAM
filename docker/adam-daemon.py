#!/usr/bin/env python3
"""ADAM Agent Daemon — Lance tous les agents et publie en temps réel"""
import subprocess, time, json, urllib.request, sys, os
from pathlib import Path
from datetime import datetime, timezone

BASE = Path(os.environ.get("ADAM_V2_DIR", "/home/aza/eva-adam-v2"))
GO_BUS = "http://localhost:8086/api/publish"
LOG_FILE = Path("/tmp/adam-daemon.log")
PID_FILE = Path("/tmp/adam-daemon.pid")

AGENTS = {
    "praetor": "agents/praetor/praetor-watch.sh",
    "sentinel": "agents/sentinel/sentinel-watch.sh",
    "critic": "agents/critic/critic-review.sh",
    "scribe": "agents/scribe/scribe-write.sh",
    "skillsmith": "agents/skillsmith/skillsmith-create.sh",
    "doctor": "agents/doctor/doctor-watch.sh",
    "treasurer": "agents/treasurer/treasurer-track.py",
    "social": "agents/social/social-manage.py",
    "osint": "agents/osint/osint-handler.py",
    "researcher": "agents/researcher/researcher-scan.py",
    "rag": "agents/rag/rag-handler.py",
    "viz": "agents/viz/viz-checker.py",
    "ctf": "agents/ctf/adam-ctf.py",
    "blue-team": "agents/blue-team/blue-watch.sh",
    "red-team": "agents/red-team/red-watch.sh",
}

def log(m):
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"[{ts}] {m}", flush=True)

def bus(topic, source, payload):
    try:
        d = json.dumps({"topic":topic,"source":source,"payload":payload,"priority":1}).encode()
        req = urllib.request.Request(GO_BUS, data=d, headers={"Content-Type":"application/json"})
        urllib.request.urlopen(req, timeout=5)
    except: pass

import threading

def packet_stream():
    """Publie un flux continu de paquets pour la visualisation temps reel"""
    import random
    actions = ["scan", "analyze", "process", "monitor", "report", "update"]
    sources = ["blue-team", "sentinel", "praetor", "critic", "doctor", "red-team"]
    while True:
        src = random.choice(sources)
        act = random.choice(actions)
        bus(f"adam:packet", src, {"action": act, "status": "running", "ts": datetime.now(timezone.utc).isoformat()})
        time.sleep(3.0)

threading.Thread(target=packet_stream, daemon=True).start()

def main():
    log(f"ADAM Daemon started — {len(AGENTS)} agents")
    bus("adam:daemon", "system", {"status":"started","agents":len(AGENTS)})
    cycle = 0
    while True:
        log(f"--- Cycle {cycle} ---")
        for name, script in AGENTS.items():
            path = BASE / script
            if path.exists():
                try:
                    r = subprocess.run([str(path)], capture_output=True, text=True, timeout=30,
                        env={**os.environ, "ADAM_V2_DIR": str(BASE), "GO_BUS_URL": GO_BUS})
                    out = (r.stdout+r.stderr)[:200]
                    bus(f"adam:packet", name, {"status":"done" if r.returncode==0 else "failed","exit":r.returncode,"output":out,"time":datetime.now(timezone.utc).isoformat()})
                    log(f"{name}: exit={r.returncode}")
                except subprocess.TimeoutExpired:
                    bus(f"adam:packet", name, {"status":"timeout"})
                    log(f"{name}: timeout")
            time.sleep(1)
        bus("adam:daemon:tick", "system", {"cycle":cycle,"time":datetime.now(timezone.utc).isoformat()})
        cycle += 1
        time.sleep(30)

if __name__ == "__main__":
    PID_FILE.write_text(str(os.getpid()))
    try: main()
    except: PID_FILE.unlink(missing_ok=True)
