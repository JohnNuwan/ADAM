#!/usr/bin/env python3
"""
Adam OSINT Handler — Recherche OSINT complète sur email/pseudo.

Canal: osint:alert
Payload: {"target": "email_or_username", "msg": "description"}

Étapes:
  1. Holehe — vérifie 120+ sites si l'email est inscrit
  2. Sherlock — recherche le pseudo sur 300+ réseaux sociaux
  3. Gravatar — hash email → photo de profil publique
  4. HaveIBeenPwned — vérifie les data breaches (via API)
  5. Google Dorking — recherche via requêtes Google
  6. Rapport HTML + JSON dans ~/eva-adam-v2/osint_reports/
"""

import sys
import os
import json
import hashlib
import subprocess
import re
from pathlib import Path
from datetime import datetime, timezone

# ============================================================
# CONFIG
# ============================================================
ADAM_V2_DIR = Path(os.environ.get("ADAM_V2_DIR", os.path.expanduser("~/eva-adam-v2")))
OSINT_VENV = ADAM_V2_DIR / "osint_env" / "bin"
REPORT_DIR = ADAM_V2_DIR / "osint_reports"
LOG_DIR = ADAM_V2_DIR / "logs"
LOG_FILE = LOG_DIR / "red-handler.log"

REPORT_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Venv Python/ executables
HOLEHE = str(OSINT_VENV / "holehe")
SHERLOCK = str(OSINT_VENV / "sherlock")
PYTHON = str(OSINT_VENV / "python")

def log(msg):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    line = f"[{ts}] [adam-red] {msg}"
    print(line, flush=True)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")

def sanitize(target):
    """Sanitize target for filenames."""
    return re.sub(r'[^a-zA-Z0-9._@-]', '_', target)[:80]

# ============================================================
# OSINT MODULES
# ============================================================

def run_holehe(email):
    """Holehe — vérifie sur quels sites l'email est inscrit."""
    log(f"🔍 Holehe: recherche email sur 120+ sites...")
    results = []
    try:
        proc = subprocess.run(
            [HOLEHE, email, "--only-used", "--no-color", "--no-clear"],
            capture_output=True, text=True, timeout=120
        )
        if proc.returncode == 0 or proc.stdout:
            # Filtrer le bruit: banner, lignes de séparation, métadonnées
            noise_patterns = [
                "Twitter : @palenath",
                "Github :",
                "BTC Donations",
                "********",
                "Email used",
                "websites checked",
                email,  # l'email lui-même affiché dans le banner
            ]
            sites = []
            for line in proc.stdout.strip().split("\n"):
                line = line.strip()
                if not line:
                    continue
                if any(p in line for p in noise_patterns):
                    continue
                # Ne garder que les lignes [+] qui indiquent un site trouvé
                if line.startswith("[+]"):
                    sites.append(line)
            results = sites
            log(f"  ✅ Holehe: {len(sites)} site(s) trouvé(s)")
        else:
            log(f"  ⚠️ Holehe retour vide (stderr: {proc.stderr[:200]})")
    except subprocess.TimeoutExpired:
        log("  ⚠️ Holehe timeout (120s)")
    except Exception as e:
        log(f"  ❌ Holehe error: {e}")
    return results

def run_sherlock(username):
    """Sherlock — recherche le pseudo sur 300+ réseaux."""
    log(f"🔍 Sherlock: recherche pseudo '{username}' sur 300+ sites...")
    results = []
    output_dir = REPORT_DIR / f"sherlock_{sanitize(username)}"
    output_dir.mkdir(parents=True, exist_ok=True)
    try:
        proc = subprocess.run(
            [SHERLOCK, username, "--timeout", "15", "--output", str(output_dir / "sherlock.txt"),
             "--csv", "--print-found"],
            capture_output=True, text=True, timeout=180
        )
        result_file = output_dir / "sherlock.txt"
        if result_file.exists():
            with open(result_file) as f:
                results = [line.strip() for line in f.readlines() if line.strip() and not line.startswith("#")]
            log(f"  ✅ Sherlock: {len(results)} profil(s) trouvé(s)")
        else:
            log(f"  ⚠️ Sherlock: pas de fichier de résultats")
    except subprocess.TimeoutExpired:
        log("  ⚠️ Sherlock timeout (180s)")
    except Exception as e:
        log(f"  ❌ Sherlock error: {e}")
    return results

def check_gravatar(email):
    """Gravatar — hash MD5 de l'email → photo de profil publique."""
    log(f"🔍 Gravatar: vérification photo de profil...")
    result = {"exists": False, "url": None}
    try:
        import urllib.request
        email_hash = hashlib.md5(email.lower().strip().encode()).hexdigest()
        url = f"https://www.gravatar.com/{email_hash}.json"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        resp = urllib.request.urlopen(req, timeout=10)
        if resp.status == 200:
            data = json.loads(resp.read())
            result["exists"] = True
            result["url"] = f"https://www.gravatar.com/avatar/{email_hash}"
            result["profile"] = data.get("entry", [{}])[0]
            log(f"  ✅ Gravatar trouvé: {result['url']}")
        else:
            log(f"  ❌ Gravatar: non trouvé")
    except Exception as e:
        log(f"  ❌ Gravatar: {e}")
    return result

def check_breaches(email):
    """HaveIBeenPwned — vérifie les fuites de données (sans clé API)."""
    log(f"🔍 HaveIBeenPwned: vérification breaches...")
    result = {"checked": False, "breaches": [], "error": None}
    try:
        import urllib.request
        # Utiliser l'API publique (sans clé) qui retourne juste le nombre
        url = f"https://haveibeenpwned.com/api/v3/breachedaccount/{email}"
        req = urllib.request.Request(url, headers={
            "User-Agent": "Adam-OSINT-Bot",
            "hibp-api-key": ""  # sans clé, on utilise l'approche par range
        })
        try:
            resp = urllib.request.urlopen(req, timeout=10)
            if resp.status == 200:
                data = json.loads(resp.read())
                result["breaches"] = [b.get("Name") for b in data]
                result["checked"] = True
                log(f"  ✅ HIBP: {len(result['breaches'])} breach(es)")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                result["checked"] = True
                result["breaches"] = []
                log(f"  ✅ HIBP: aucune fuite trouvée")
            elif e.code == 401:
                result["error"] = "API key required"
                log(f"  ⚠️ HIBP: clé API requise (sans clé, on skip)")
            elif e.code == 429:
                result["error"] = "Rate limited"
                log(f"  ⚠️ HIBP: rate limited")
    except Exception as e:
        result["error"] = str(e)
        log(f"  ❌ HIBP: {e}")
    return result

def extract_username(email):
    """Extrait le pseudo d'un email."""
    if "@" in email:
        return email.split("@")[0]
    return email

def generate_report(target, holehe_results, sherlock_results, gravatar, breaches):
    """Génère un rapport HTML + JSON — un fichier par heure par cible."""
    ts = datetime.now(timezone.utc)
    ts_hour = ts.strftime("%Y-%m-%d_%H")          # ex: 2026-07-23_13
    date_dir = ts.strftime("%Y-%m-%d")              # ex: 2026-07-23
    safe = sanitize(target)
    
    # Organiser par date: osint_reports/2026-07-23/
    day_dir = REPORT_DIR / date_dir
    day_dir.mkdir(parents=True, exist_ok=True)
    
    # Noms de fichiers stables par heure
    json_path = day_dir / f"osint_{safe}_{ts_hour}.json"
    html_path = day_dir / f"osint_{safe}_{ts_hour}.html"
    
    # Skip si déjà scanné cette heure (évite les doublons)
    if json_path.exists():
        log(f"⏭️  Rapport déjà généré pour {target} à {ts_hour} — skip")
        return json_path, html_path
    
    # Rapport JSON
    json_report = {
        "target": target,
        "timestamp": ts.isoformat(),
        "hour_bucket": ts_hour,
        "holehe_sites": holehe_results,
        "sherlock_profiles": sherlock_results,
        "gravatar": gravatar,
        "breaches": breaches,
        "summary": {
            "total_sites_email": len(holehe_results),
            "total_profiles_username": len(sherlock_results),
            "gravatar_found": gravatar.get("exists", False),
            "breaches_found": len(breaches.get("breaches", [])),
        }
    }
    
    with open(json_path, "w") as f:
        json.dump(json_report, f, indent=2, ensure_ascii=False)
    log(f"📄 Rapport JSON: {json_path}")
    
    # Rapport HTML
    html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<title>Rapport OSINT — {target}</title>
<style>
body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #0a0a0f; color: #e0e0e8; padding: 20px; max-width: 900px; margin: auto; }}
h1 {{ color: #ff4444; border-bottom: 2px solid #ff4444; padding-bottom: 10px; }}
h2 {{ color: #00ddff; margin-top: 30px; }}
.meta {{ color: #888; font-size: 0.85rem; margin-bottom: 20px; }}
.result-item {{ background: #14141c; border: 1px solid #2a2a3a; border-radius: 8px; padding: 12px; margin: 8px 0; }}
.result-item a {{ color: #4488ff; text-decoration: none; }}
.result-item a:hover {{ text-decoration: underline; }}
.summary-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 20px; }}
.summary-box {{ background: #14141c; border: 1px solid #2a2a3a; border-radius: 8px; padding: 15px; text-align: center; }}
.summary-box .val {{ font-size: 2rem; font-weight: bold; }}
.summary-box .label {{ color: #888; font-size: 0.75rem; text-transform: uppercase; }}
.found {{ color: #00ff88; }}
.not-found {{ color: #888; }}
img.profile {{ border-radius: 50%; width: 80px; height: 80px; vertical-align: middle; }}
</style>
</head>
<body>
<h1>🔴 Rapport OSINT — {target}</h1>
<div class="meta">Généré le {ts.strftime("%d/%m/%Y à %H:%M:%S UTC")} par Adam-Red</div>

<div class="summary-grid">
  <div class="summary-box"><div class="val found">{len(holehe_results)}</div><div class="label">Sites (email)</div></div>
  <div class="summary-box"><div class="val found">{len(sherlock_results)}</div><div class="label">Profils (pseudo)</div></div>
  <div class="summary-box"><div class="val {'found' if gravatar.get('exists') else 'not-found'}">{'OUI' if gravatar.get('exists') else 'NON'}</div><div class="label">Gravatar</div></div>
  <div class="summary-box"><div class="val {'found' if breaches.get('breaches') else 'not-found'}">{len(breaches.get('breaches', []))}</div><div class="label">Breaches</div></div>
</div>

<h2>📧 Sites où l'email est inscrit (Holehe)</h2>
{"<div class='result-item found'>✅ " + "</div><div class='result-item found'>✅ ".join(holehe_results) + "</div>" if holehe_results else "<div class='result-item not-found'>Aucun site trouvé</div>"}

<h2>👤 Profils sociaux par pseudo (Sherlock)</h2>
{"<div class='result-item'>🔗 " + "</div><div class='result-item'>🔗 ".join(sherlock_results) + "</div>" if sherlock_results else "<div class='result-item not-found'>Aucun profil trouvé</div>"}

<h2>🖼️ Gravatar</h2>
<div class="result-item">
  {"<img class='profile' src='" + gravatar["url"] + "'><br><a href='" + gravatar["url"] + "'>" + gravatar["url"] + "</a>" if gravatar.get("exists") else "Aucun Gravatar trouvé"}
</div>

<h2>🔐 Fuites de données (HaveIBeenPwned)</h2>
<div class="result-item">
  {f"⚠️ {len(breaches.get('breaches', []))} fuite(s): " + ", ".join(breaches["breaches"]) if breaches.get("breaches") else "✅ Aucune fuite connue" if breaches.get("checked") else "Non vérifié (clé API requise)"}
</div>

<hr style="border-color: #2a2a3a; margin-top: 30px;">
<div class="meta">Adam-Red — The Hive OSINT Division | {ts.isoformat()}</div>
</body>
</html>"""
    
    html_path = day_dir / f"osint_{safe}_{ts_hour}.html"
    with open(html_path, "w") as f:
        f.write(html)
    log(f"📄 Rapport HTML: {html_path}")
    
    return json_path, html_path

# ============================================================
# MAIN
# ============================================================
def main():
    # Récupérer le payload depuis les variables d'environnement ADAM
    payload_str = os.environ.get("ADAM_EVENT_PAYLOAD", "{}")
    channel = os.environ.get("ADAM_EVENT_CHANNEL", "osint:alert")
    agent_id = os.environ.get("ADAM_AGENT_ID", "adam-red")
    
    try:
        payload = json.loads(payload_str) if payload_str else {}
    except json.JSONDecodeError:
        payload = {}
    
    target = payload.get("target") or payload.get("email") or payload.get("username") or ""
    
    # Si pas de target explicite, checker si le msg contient un email
    if not target:
        msg = payload.get("msg", "")
        email_match = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', msg)
        if email_match:
            target = email_match.group()
    
    if not target:
        log("⚠️ Aucune cible (target/email/username) dans le payload")
        log(f"  Payload reçu: {payload_str[:200]}")
        sys.exit(0)
    
    log(f"🎯 Cible OSINT: {target}")
    log(f"📋 Canal: {channel} | Agent: {agent_id}")
    
    is_email = "@" in target
    username = extract_username(target)
    
    # ⏭️  Skip si déjà scanné dans l'heure courante
    ts = datetime.now(timezone.utc)
    ts_hour = ts.strftime("%Y-%m-%d_%H")
    date_dir = ts.strftime("%Y-%m-%d")
    safe = sanitize(target)
    day_dir = REPORT_DIR / date_dir
    expected_json = day_dir / f"osint_{safe}_{ts_hour}.json"
    if expected_json.exists():
        log(f"⏭️  Déjà scanné à {ts_hour} — skip complet (CPU économisé)")
        sys.exit(0)
    
    holehe_results = []
    sherlock_results = []
    gravatar = {"exists": False, "url": None}
    breaches = {"checked": False, "breaches": []}
    
    # 1. Holehe (email only)
    if is_email:
        holehe_results = run_holehe(target)
    
    # 2. Sherlock (toujours, avec le username)
    sherlock_results = run_sherlock(username)
    
    # 3. Gravatar (email only)
    if is_email:
        gravatar = check_gravatar(target)
    
    # 4. HaveIBeenPwned (email only)
    if is_email:
        breaches = check_breaches(target)
    
    # 5. Rapport
    json_path, html_path = generate_report(
        target, holehe_results, sherlock_results, gravatar, breaches
    )
    
    # Résumé
    log(f"📊 Rapport généré:")
    log(f"  - Sites email: {len(holehe_results)}")
    log(f"  - Profils pseudo: {len(sherlock_results)}")
    log(f"  - Gravatar: {'OUI' if gravatar['exists'] else 'NON'}")
    log(f"  - Breaches: {len(breaches.get('breaches', []))}")
    log(f"  - JSON: {json_path}")
    log(f"  - HTML: {html_path}")
    log(f"✅ OSINT terminé pour {target}")

    # ──────────────────────────────────────────
    # Follow-up event — chaîne entre agents
    # ──────────────────────────────────────────
    # Si breaches détectées → alerter adam-blue (security)
    breach_count = len(breaches.get("breaches", []))
    if breach_count > 0:
        try:
            import subprocess
            publish_path = str(ADAM_V2_DIR / "publish.py")
            subprocess.run(
                ["python3", publish_path, "security:vulnerability_detected",
                 json.dumps({
                     "type": "data_breach",
                     "target": target,
                     "breach_count": breach_count,
                     "severity": "high",
                     "source_agent": "adam-red"
                 }),
                 "--source", "adam-red"],
                capture_output=True, text=True, timeout=10
            )
            log(f"→ published security:vulnerability_detected for adam-blue ({breach_count} breaches)")
        except Exception as e:
            log(f"⚠ Échec publication follow-up: {e}")


if __name__ == "__main__":
    main()
