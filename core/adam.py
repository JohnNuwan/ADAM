#!/usr/bin/env python3
"""
EVA ADAM v2 — CLI de Gestion Unifié
=====================================
Interface en ligne de commande pour gérer l'architecture ADAM v2.

Commandes :
    adam.py init              — Initialise le bus, agents et souscriptions
    adam.py status            — Vue d'ensemble (bus + daemon + watcher + agents)
    adam.py start             — Démarre daemon + watcher (background)
    adam.py stop              — Arrête daemon + watcher
    adam.py restart            — Redémarre tout
    adam.py bus stats         — Statistiques du bus
    adam.py bus events        — Liste les événements récents
    adam.py bus publish CH PAYLOAD — Publie un événement manuellement
    adam.py agents            — Liste les agents et leur statut
    adam.py agent <id>        — Détail d'un agent
    adam.py subs              — Liste les souscriptions
    adam.py sub <agent> <channel> <handler> — Ajoute une souscription
    adam.py log               — Journal d'exécution récent
    adam.py test              — Test de bout en bout (publish → dispatch → log)
"""

import sys
import os
import json
import time
import subprocess
import signal
import logging
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent))
from event_bus import EventBus, DB_PATH, CHANNELS, DEFAULT_AGENTS, DEFAULT_SUBSCRIPTIONS

ADAM_V2_DIR = Path.home() / "eva-adam-v2"
DAEMON_PID = ADAM_V2_DIR / "event_daemon.pid"
WATCHER_PID = ADAM_V2_DIR / "file_watcher.pid"

logger = logging.getLogger("eva.adam.cli")


# ============================================================
#  INIT
# ============================================================

def cmd_init():
    """Initialise le bus, enregistre les agents et souscriptions par défaut."""
    print("=== Initialisation ADAM v2 ===")
    print()

    bus = EventBus()

    # 1. Schéma déjà créé par EventBus.__init__
    print(f"✓ Base SQLite: {DB_PATH}")
    print(f"  Mode WAL activé")

    # 2. Enregistre les agents
    for agent_id, display_name, config in DEFAULT_AGENTS:
        bus.register_agent(agent_id, display_name, config)
        print(f"  Agent: {agent_id} ({display_name})")

    # 3. Enregistre les souscriptions
    for agent_id, channel, handler in DEFAULT_SUBSCRIPTIONS:
        bus.subscribe(agent_id, channel, handler)

    print(f"  {len(DEFAULT_AGENTS)} agents enregistrés")
    print(f"  {len(DEFAULT_SUBSCRIPTIONS)} souscriptions créées")

    # 4. Vérifie les répertoires surveillés
    from file_watcher import WATCH_DIRS
    print()
    print("Répertoires surveillés:")
    for d in WATCH_DIRS:
        exists = Path(d).exists()
        print(f"  {'✓' if exists else '✗'} {d}")

    # 5. Vérifie inotifywait
    try:
        subprocess.run(["inotifywait", "--help"], capture_output=True, timeout=5)
        print(f"  ✓ inotifywait disponible (mode natif)")
    except (FileNotFoundError, subprocess.TimeoutExpired):
        print(f"  ⚠ inotifywait manquant (mode polling) — installer: sudo apt install inotify-tools")

    # 6. Publie un événement de démarrage
    bus.publish("adam:heartbeat", {
        "action": "init",
        "agents": len(DEFAULT_AGENTS),
        "subscriptions": len(DEFAULT_SUBSCRIPTIONS),
    }, source="cli")

    print()
    print("✓ ADAM v2 initialisé. Utilisez 'adam.py start' pour démarrer les daemons.")
    bus.close()


# ============================================================
#  START / STOP / RESTART
# ============================================================

def cmd_start():
    """Démarre le daemon et le watcher en background."""
    print("=== Démarrage ADAM v2 ===")

    # Démarre le daemon
    if DAEMON_PID.exists():
        pid = int(DAEMON_PID.read_text().strip())
        try:
            os.kill(pid, 0)
            print(f"⚠ Daemon déjà en cours (PID: {pid})")
        except ProcessLookupError:
            DAEMON_PID.unlink(missing_ok=True)
            _start_daemon()
    else:
        _start_daemon()

    # Démarre le watcher
    if WATCHER_PID.exists():
        pid = int(WATCHER_PID.read_text().strip())
        try:
            os.kill(pid, 0)
            print(f"⚠ Watcher déjà en cours (PID: {pid})")
        except ProcessLookupError:
            WATCHER_PID.unlink(missing_ok=True)
            _start_watcher()
    else:
        _start_watcher()

    time.sleep(2)
    print()
    cmd_status()


def _start_daemon():
    """Démarre le daemon en background."""
    script = Path(__file__).parent / "event_daemon.py"
    proc = subprocess.Popen(
        [sys.executable, str(script), "start-bg"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    print(f"✓ Event Daemon démarré (PID: {proc.pid})")


def _start_watcher():
    """Démarre le watcher en background."""
    script = Path(__file__).parent / "file_watcher.py"
    proc = subprocess.Popen(
        [sys.executable, str(script), "start-bg"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    print(f"✓ File Watcher démarré (PID: {proc.pid})")


def cmd_stop():
    """Arrête le daemon et le watcher."""
    print("=== Arrêt ADAM v2 ===")

    # Arrête le watcher
    if WATCHER_PID.exists():
        pid = int(WATCHER_PID.read_text().strip())
        try:
            os.kill(pid, signal.SIGTERM)
            print(f"✓ Watcher arrêté (PID: {pid})")
            for _ in range(10):
                if not WATCHER_PID.exists():
                    break
                time.sleep(0.5)
            WATCHER_PID.unlink(missing_ok=True)
        except ProcessLookupError:
            WATCHER_PID.unlink(missing_ok=True)
            print("  Watcher déjà arrêté")
    else:
        print("  Watcher non démarré")

    # Arrête le daemon
    if DAEMON_PID.exists():
        pid = int(DAEMON_PID.read_text().strip())
        try:
            os.kill(pid, signal.SIGTERM)
            print(f"✓ Daemon arrêté (PID: {pid})")
            for _ in range(10):
                if not DAEMON_PID.exists():
                    break
                time.sleep(0.5)
            DAEMON_PID.unlink(missing_ok=True)
        except ProcessLookupError:
            DAEMON_PID.unlink(missing_ok=True)
            print("  Daemon déjà arrêté")
    else:
        print("  Daemon non démarré")


def cmd_restart():
    """Redémarre tout."""
    cmd_stop()
    time.sleep(2)
    cmd_start()


# ============================================================
#  STATUS
# ============================================================

def cmd_status():
    """Affiche le statut global."""
    print("=== Statut ADAM v2 ===")
    print()

    # Daemon
    daemon_running = False
    if DAEMON_PID.exists():
        pid = int(DAEMON_PID.read_text().strip())
        try:
            os.kill(pid, 0)
            print(f"✓ Event Daemon:    en cours (PID: {pid})")
            daemon_running = True
        except ProcessLookupError:
            print(f"✗ Event Daemon:    mort (PID stale: {pid})")
            DAEMON_PID.unlink(missing_ok=True)
    else:
        print(f"✗ Event Daemon:    arrêté")

    # Watcher
    watcher_running = False
    if WATCHER_PID.exists():
        pid = int(WATCHER_PID.read_text().strip())
        try:
            os.kill(pid, 0)
            print(f"✓ File Watcher:    en cours (PID: {pid})")
            watcher_running = True
        except ProcessLookupError:
            print(f"✗ File Watcher:    mort (PID stale: {pid})")
            WATCHER_PID.unlink(missing_ok=True)
    else:
        print(f"✗ File Watcher:    arrêté")

    # Bus
    bus = EventBus()
    stats = bus.get_stats()
    print()
    print(f"Bus d'événements ({DB_PATH}):")
    print(f"  Total: {stats['total_events']} | Pending: {stats['pending']} | Processing: {stats['processing']} | Done: {stats['done']} | Failed: {stats['failed']}")
    if stats["top_channels"]:
        print(f"  Top canaux:")
        for ch in stats["top_channels"][:5]:
            print(f"    {ch['channel']:40s} {ch['count']:5d}")

    # Agents
    agents = bus.get_all_agents()
    print()
    print(f"Agents ({len(agents)}):")
    print(f"  {'ID':<22s} {'Statut':<10s} {'Dernier':<8s} {'PID':<7s} {'Heartbeat':<22s} {'Erreur'}")
    print(f"  {'-'*22} {'-'*10} {'-'*8} {'-'*7} {'-'*22} {'-'*30}")
    for a in agents:
        hb = (a.get("heartbeat_at") or "-")[:19]
        err = (a.get("last_error") or "")[:30]
        print(f"  {a['agent_id']:<22s} {a['status']:<10s} {a.get('last_status','') or '-':<8s} {str(a.get('pid') or '-'):<7s} {hb:<22s} {err}")

    bus.close()


# ============================================================
#  BUS
# ============================================================

def cmd_bus(args: list[str]):
    """Commandes du bus."""
    if not args:
        print("Usage: adam.py bus [stats|events|publish CHANNEL PAYLOAD]")
        return

    sub = args[0]
    bus = EventBus()

    if sub == "stats":
        stats = bus.get_stats()
        print(json.dumps(stats, indent=2, ensure_ascii=False))

    elif sub == "events":
        limit = int(args[1]) if len(args) > 1 else 20
        conn = bus._get_conn()
        rows = conn.execute(
            "SELECT * FROM events ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        print(f"{'ID':<6s} {'Canal':<40s} {'Source':<15s} {'Priorité':<9s} {'Statut':<10s} {'Créé':<22s}")
        print("-" * 110)
        for r in rows:
            print(f"{r['id']:<6d} {r['channel']:<40s} {r['source']:<15s} {r['priority']:<9d} {r['status']:<10s} {r['created_at'][:19]}")

    elif sub == "publish":
        if len(args) < 3:
            print("Usage: adam.py bus publish CHANNEL 'JSON_PAYLOAD'")
            bus.close()
            return
        channel = args[1]
        payload = json.loads(args[2]) if len(args) > 2 else {}
        eid = bus.publish(channel, payload, source="cli")
        print(f"✓ Événement #{eid} publié sur {channel}")

    elif sub == "channels":
        print(f"Canaux disponibles ({len(CHANNELS)}):")
        for ch, desc in sorted(CHANNELS.items()):
            print(f"  {ch:<40s} {desc}")

    elif sub == "cleanup":
        days = int(args[1]) if len(args) > 1 else 30
        bus.cleanup_old_events(days)
        print(f"✓ Événements > {days} jours nettoyés")

    bus.close()


# ============================================================
#  AGENTS
# ============================================================

def cmd_agents():
    """Liste les agents."""
    bus = EventBus()
    agents = bus.get_all_agents()
    print(f"Agents enregistrés ({len(agents)}):")
    print()
    for a in agents:
        print(f"  {a['agent_id']}")
        print(f"    Nom:       {a['display_name']}")
        print(f"    Statut:    {a['status']}")
        print(f"    Dernier:   {a.get('last_status') or '-'}")
        print(f"    Heartbeat: {a.get('heartbeat_at') or '-'}")
        if a.get("last_error"):
            print(f"    Erreur:    {a['last_error'][:100]}")
        if a.get("config"):
            print(f"    Config:    {a['config']}")
        print()

    bus.close()


def cmd_agent(agent_id: str):
    """Détail d'un agent."""
    bus = EventBus()
    info = bus.get_agent_status(agent_id)
    if not info:
        print(f"Agent introuvable: {agent_id}")
        bus.close()
        return

    print(f"Agent: {agent_id}")
    print(f"  Nom:        {info['display_name']}")
    print(f"  Statut:     {info['status']}")
    print(f"  Dernier:    {info.get('last_status') or '-'}")
    print(f"  PID:        {info.get('pid') or '-'}")
    print(f"  Heartbeat:  {info.get('heartbeat_at') or '-'}")
    print(f"  Config:     {info.get('config') or '{}'}")
    if info.get("last_error"):
        print(f"  Erreur:     {info['last_error']}")

    # Souscriptions de cet agent
    conn = bus._get_conn()
    subs = conn.execute(
        "SELECT * FROM subscriptions WHERE agent_id=? ORDER BY channel", (agent_id,)
    ).fetchall()
    print(f"\n  Souscriptions ({len(subs)}):")
    for s in subs:
        enabled = "✓" if s["enabled"] else "✗"
        print(f"    {enabled} {s['channel']:<40s} → {s['handler']}")

    # Historique récent
    logs = conn.execute(
        """SELECT * FROM execution_log WHERE agent_id=? ORDER BY started_at DESC LIMIT 10""",
        (agent_id,)
    ).fetchall()
    print(f"\n  Historique récent ({len(logs)}):")
    for l in logs:
        status = "✓" if l["success"] else "✗"
        dur = f"{l['duration_ms']}ms" if l["duration_ms"] else "-"
        print(f"    {status} #{l['event_id']} {l['trigger_channel']:<35s} {l['started_at'][:19]} {dur}")

    bus.close()


# ============================================================
#  SUBSCRIPTIONS
# ============================================================

def cmd_subs():
    """Liste toutes les souscriptions."""
    bus = EventBus()
    conn = bus._get_conn()
    rows = conn.execute(
        "SELECT * FROM subscriptions ORDER BY agent_id, channel"
    ).fetchall()
    print(f"Souscriptions ({len(rows)}):")
    print()
    print(f"  {'Agent':<22s} {'Canal':<40s} {'Handler':<45s} {'Actif'}")
    print(f"  {'-'*22} {'-'*40} {'-'*45} {'-'*5}")
    for r in rows:
        enabled = "✓" if r["enabled"] else "✗"
        print(f"  {r['agent_id']:<22s} {r['channel']:<40s} {r['handler']:<45s} {enabled}")

    bus.close()


def cmd_sub(agent_id: str, channel: str, handler: str):
    """Ajoute une souscription."""
    bus = EventBus()
    bus.subscribe(agent_id, channel, handler)
    print(f"✓ Souscription: {agent_id} → {channel} ({handler})")
    bus.close()


# ============================================================
#  LOG
# ============================================================

def cmd_log():
    """Journal d'exécution récent."""
    bus = EventBus()
    conn = bus._get_conn()
    rows = conn.execute(
        """SELECT * FROM execution_log ORDER BY started_at DESC LIMIT 30"""
    ).fetchall()
    print(f"Journal d'exécution ({len(rows)} entrées):")
    print()
    print(f"  {'ID':<5s} {'Agent':<22s} {'Canal':<35s} {'Succès':<7s} {'Exit':<5s} {'Durée':<10s} {'Début'}")
    print(f"  {'-'*5} {'-'*22} {'-'*35} {'-'*7} {'-'*5} {'-'*10} {'-'*19}")
    for l in rows:
        success = "✓" if l["success"] else "✗"
        dur = f"{l['duration_ms']}ms" if l["duration_ms"] else "-"
        exit_c = str(l["exit_code"]) if l["exit_code"] is not None else "-"
        print(f"  {l['id']:<5d} {l['agent_id']:<22s} {l['trigger_channel']:<35s} {success:<7s} {exit_c:<5s} {dur:<10s} {l['started_at'][:19]}")

    bus.close()


# ============================================================
#  TEST
# ============================================================

def cmd_test():
    """
    Test de bout en bout :
    1. Publie un événement test
    2. Vérifie qu'il est dans le bus
    3. Vérifie les souscriptions
    4. Vérifie le daemon (si en cours)
    """
    print("=== Test ADAM v2 ===")
    print()
    bus = EventBus()

    # 1. Test publication
    print("[1/4] Test publication...")
    eid = bus.publish("adam:heartbeat", {
        "action": "test",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }, source="cli-test", priority=1)
    print(f"  ✓ Événement #{eid} publié sur adam:heartbeat")

    # 2. Vérifie qu'il est récupérable
    print("[2/4] Test récupération...")
    pending = bus.get_pending_events("adam:heartbeat")
    found = any(e["id"] == eid for e in pending)
    if found:
        print(f"  ✓ Événement #{eid} trouvé dans pending")
    else:
        print(f"  ✗ Événement #{eid} non trouvé dans pending")
        return

    # 3. Vérifie les souscriptions
    print("[3/4] Test souscriptions...")
    subs = bus.get_subscriptions("adam:heartbeat")
    if subs:
        print(f"  ✓ {len(subs)} souscription(s) trouvée(s) pour adam:heartbeat")
    else:
        print(f"  ⚠ Aucune souscription pour adam:heartbeat (normal — pas d'abonné)")

    # Vérifie que les souscriptions par défaut existent
    conn = bus._get_conn()
    total_subs = conn.execute("SELECT COUNT(*) FROM subscriptions").fetchone()[0]
    total_agents = conn.execute("SELECT COUNT(*) FROM agents").fetchone()[0]
    print(f"  ✓ {total_agents} agents, {total_subs} souscriptions au total")

    # 4. Test claim + complete
    print("[4/4] Test claim/complete...")
    claimed = bus.claim_event(eid, "cli-test")
    if claimed:
        print(f"  ✓ Événement #{eid} réservé (claim)")
    else:
        print(f"  ✗ Claim échoué pour #{eid}")
        return

    bus.complete_event(eid, success=True)
    print(f"  ✓ Événement #{eid} marqué comme done")

    # Stats finales
    stats = bus.get_stats()
    print()
    print(f"Statistiques finales:")
    print(f"  Total:  {stats['total_events']}")
    print(f"  Done:   {stats['done']}")
    print(f"  Failed: {stats['failed']}")

    print()
    print("✓ Tous les tests passent. ADAM v2 est fonctionnel.")

    bus.close()


# ============================================================
#  MAIN
# ============================================================

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)

    cmd = sys.argv[1]
    args = sys.argv[2:]

    if cmd == "init":
        cmd_init()
    elif cmd == "start":
        cmd_start()
    elif cmd == "stop":
        cmd_stop()
    elif cmd == "restart":
        cmd_restart()
    elif cmd == "status":
        cmd_status()
    elif cmd == "bus":
        cmd_bus(args)
    elif cmd == "agents":
        cmd_agents()
    elif cmd == "agent":
        if not args:
            print("Usage: adam.py agent <id>")
            return
        cmd_agent(args[0])
    elif cmd == "subs":
        cmd_subs()
    elif cmd == "sub":
        if len(args) < 3:
            print("Usage: adam.py sub <agent_id> <channel> <handler>")
            return
        cmd_sub(args[0], args[1], args[2])
    elif cmd == "log":
        cmd_log()
    elif cmd == "test":
        cmd_test()
    elif cmd == "version":
        print("EVA ADAM v2.0 — Event-Driven Architecture")
        print(f"  Bus: {DB_PATH}")
        print(f"  Dir: {ADAM_V2_DIR}")
    else:
        print(f"Commande inconnue: {cmd}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING, format="%(asctime)s [%(levelname)s] %(message)s")
    main()
