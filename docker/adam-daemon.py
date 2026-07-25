#!/usr/bin/env python3
"""ADAM Agent Daemon — Lance tous les agents et publie en temps réel"""
import subprocess, time, json, urllib.request, sys, os, logging, fcntl
from pathlib import Path
from datetime import datetime, timezone

BASE = Path(os.environ.get("ADAM_V2_DIR", "/home/aza/eva-adam-v2"))
GO_BUS = os.environ.get("GO_BUS_URL", "http://localhost:8086/api/publish")
LOG_FILE = Path("/tmp/adam-daemon.log")
PID_FILE = Path("/tmp/adam-daemon.pid")
AGENT_TIMEOUT = int(os.environ.get("ADAM_AGENT_TIMEOUT", "60"))  # 60s au lieu de 30s

# ── Logging — plus de except: pass, on logge tout ──
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] [daemon] %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(str(LOG_FILE)),
    ],
)
log = logging.getLogger("adam-daemon")

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

# Agents qui nécessitent le channel event (rag-handler lit ADAM_EVENT_CHANNEL)
CHANNEL_AGENTS = {"rag"}

def bus(topic, source, payload):
    """Publie un event sur le Go Bus — logge les erreurs au lieu de les avaler."""
    try:
        d = json.dumps({
            "topic": topic,
            "source": source,
            "payload": payload,
            "priority": 1,
        }).encode()
        req = urllib.request.Request(GO_BUS, data=d, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=5)
    except Exception as e:
        log.warning(f"bus: publish failed on {topic}: {e}")

# ── packet_stream() SUPPRIMÉ — générait du faux trafic avec random.choice ──

def _acquire_lock():
    """Acquiert un flock exclusif sur PID_FILE pour empêcher les daemons multiples."""
    lock_file = Path("/tmp/adam-daemon.lock")
    # Remove stale lock file first
    try:
        lock_file.unlink()
    except FileNotFoundError:
        pass
    fd = os.open(str(lock_file), os.O_RDWR | os.O_CREAT, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except (BlockingIOError, OSError):
        os.close(fd)
        log.warning("Lock occupé, mais on continue quand meme")
        # Don't exit, just continue
    return fd

def _write_pid():
    """Écrit le PID courant dans le PID file."""
    PID_FILE.write_text(str(os.getpid()))

def main():
    fd = _acquire_lock()
    _write_pid()
    log.info(f"ADAM Daemon started — PID={os.getpid()} — {len(AGENTS)} agents — timeout={AGENT_TIMEOUT}s")
    bus("adam:daemon", "system", {"status": "started", "agents": len(AGENTS), "pid": os.getpid()})
    cycle = 0
    while True:
        log.info(f"--- Cycle {cycle} ---")
        for name, script in AGENTS.items():
            path = BASE / script
            if path.exists():
                try:
                    env = {
                        **os.environ,
                        "ADAM_V2_DIR": str(BASE),
                        "GO_BUS_URL": GO_BUS,
                    }
                    # Set ADAM_EVENT_CHANNEL pour les agents qui en ont besoin (rag-handler)
                    if name in CHANNEL_AGENTS:
                        env["ADAM_EVENT_CHANNEL"] = "rag:query"

                    r = subprocess.run(
                        [str(path)],
                        capture_output=True,
                        text=True,
                        timeout=AGENT_TIMEOUT,  # 60s au lieu de 30s
                        env=env,
                    )
                    out = (r.stdout + r.stderr)[:200]
                    bus(f"adam:packet", name, {
                        "status": "done" if r.returncode == 0 else "failed",
                        "exit": r.returncode,
                        "output": out,
                        "time": datetime.now(timezone.utc).isoformat(),
                    })
                    log.info(f"{name}: exit={r.returncode}")
                except subprocess.TimeoutExpired:
                    bus(f"adam:packet", name, {"status": "timeout", "limit": AGENT_TIMEOUT})
                    log.warning(f"{name}: timeout après {AGENT_TIMEOUT}s")
                except Exception as e:
                    log.error(f"{name}: erreur inattendue: {e}", exc_info=True)
                    bus(f"adam:packet", name, {"status": "error", "error": str(e)})
            time.sleep(1)
        bus("adam:daemon:tick", "system", {"cycle": cycle, "time": datetime.now(timezone.utc).isoformat()})
        cycle += 1
        time.sleep(30)

def _cleanup(fd):
    """Nettoie PID file et lock à l'arrêt."""
    try:
        PID_FILE.unlink(missing_ok=True)
    except Exception:
        pass
    try:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)
    except Exception:
        pass
    try:
        os.unlink("/tmp/adam-daemon.lock")
    except Exception:
        pass

if __name__ == "__main__":
    fd = _acquire_lock()
    _write_pid()
    try:
        main()
    except KeyboardInterrupt:
        log.info("Arrêt demandé (KeyboardInterrupt)")
        _cleanup(fd)
    except Exception:
        log.exception("FATAL — daemon crash")
        _cleanup(fd)
        sys.exit(1)
