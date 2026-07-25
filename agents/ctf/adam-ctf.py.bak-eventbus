#!/usr/bin/env python3
"""
ADAM-CTF — Agent d'entraînement CTF autonome.

Catégories gérées :
  - web     : XSS, SQLi, LFI, RCE, SSRF, IDOR, SSTI
  - crypto  : RSA, AES, hash cracking, padding oracle, XOR
  - reverse : analyse binaire, strings, décompilation statique
  - pwn     : buffer overflow, format string, ROP
  - forensic: steganography, file carving, memory dump
  - misc    : logique, encodage, scripting

Flux autonome :
  1. PICK   — Choisit un challenge dans le pool local ou distant
  2. SOLVE  — Tente de résoudre avec techniques connues + RAG
  3. VERIFY — Valide la solution (flag format)
  4. LEARN  — Stocke la solution + technique dans le RAG
  5. EVOLVE — Met à jour le fitness des stratégies

Le agent s'enregistre dans l'event bus, écoute ctf:challenge,
ctf:solved, ctf:failed, et publie ctf:learning sur le bus.
"""

import argparse
import json
import os
import re
import subprocess
import time
import base64
from datetime import datetime, timezone
from pathlib import Path

# ─── Configuration ───
AGENT_ID = "adam-ctf"
DISPLAY_NAME = "ADAM-CTF — Entraînement CTF & Apprentissage"
EVENT_DB = Path("/home/aza/eva-adam-v2/event_bus.db")
LOG_DIR = Path("/home/aza/eva-adam-v2/logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "ctf.log"
REPORT_DIR = Path("/home/aza/eva-adam-v2/reports/ctf")
REPORT_DIR.mkdir(parents=True, exist_ok=True)
CHALLENGE_DIR = Path("/home/aza/eva-adam-v2/ctf/challenges")
CHALLENGE_DIR.mkdir(parents=True, exist_ok=True)
SOLUTIONS_DIR = Path("/home/aza/eva-adam-v2/ctf/solutions")
SOLUTIONS_DIR.mkdir(parents=True, exist_ok=True)
RAG_URL = "http://localhost:8083"

# Flag format commun: flag{...}, CTF{...}, picoCTF{...}, etc.
FLAG_PATTERNS = [
    re.compile(r"flag\{[^}]+\}", re.IGNORECASE),
    re.compile(r"CTF\{[^}]+\}", re.IGNORECASE),
    re.compile(r"picoCTF\{[^}]+\}", re.IGNORECASE),
    re.compile(r"HTB\{[^}]+\}", re.IGNORECASE),
    re.compile(r"THM\{[^}]+\}", re.IGNORECASE),
    re.compile(r"FLAG_[A-Za-z0-9_]+"),
]

# ─── Utilitaires ───

def log(msg: str, level: str = "INFO"):
    ts = datetime.now(timezone.utc).isoformat()
    line = f"[{ts}] [{level}] {msg}"
    print(line, flush=True)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")

def db_conn():
    import sqlite3
    return sqlite3.connect(str(EVENT_DB))

def publish(channel: str, payload: dict, priority: int = 3):
    """Publie un event dans le bus."""
    conn = db_conn()
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT INTO events (channel, source, payload, priority, created_at, status) VALUES (?,?,?,?,?,?)",
        (channel, AGENT_ID, json.dumps(payload, ensure_ascii=False), priority, now, "pending"),
    )
    conn.commit()
    conn.close()

def heartbeat():
    """Heartbeat pour le moniteur."""
    publish("adam:heartbeat", {
        "agent_id": AGENT_ID,
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }, priority=1)

def rag_search(query: str, n: int = 5) -> list:
    """Recherche dans le RAG pour trouver des techniques similaires."""
    try:
        r = subprocess.run(
            ["curl", "-s", "-X", "POST", f"{RAG_URL}/api/rag/search",
             "-H", "Content-Type: application/json",
             "-d", json.dumps({"query": query, "n_results": n})],
            capture_output=True, text=True, timeout=10
        )
        if r.returncode == 0 and r.stdout:
            data = json.loads(r.stdout)
            return data.get("results", [])
    except Exception as e:
        log(f"RAG search échoué: {e}", "WARN")
    return []

# ─── Techniques CTF ───

TECHNIQUES = {
    "web": {
        "xss_reflected": {
            "name": "XSS Reflected",
            "patterns": ["<script>", "javascript:", "onerror=", "onload="],
            "payloads": ["<script>alert(1)</script>", "\"><img src=x onerror=alert(1)>",
                         "javascript:alert(1)", "<svg/onload=alert(1)>"],
        },
        "sqli_basic": {
            "name": "SQL Injection Basique",
            "patterns": ["'", "\"", "OR 1=1", "UNION SELECT", "' OR '1'='1"],
            "payloads": ["' OR '1'='1' --", "\" OR \"1\"=\"1\" --",
                         "' UNION SELECT NULL,NULL,NULL --", "1; DROP TABLE users --"],
        },
        "lfi_basic": {
            "name": "LFI (Local File Inclusion)",
            "patterns": ["../", "..\\", "/etc/passwd", "/proc/self/environ"],
            "payloads": ["../../../etc/passwd", "../../../../etc/shadow",
                         "php://filter/convert.base64/resource=index.php"],
        },
        "ssti_basic": {
            "name": "SSTI (Server-Side Template Injection)",
            "patterns": ["{{", "}}", "${", "#{", "<%="],
            "payloads": ["{{7*7}}", "${7*7}", "#{7*7}", "<%=7*7%>",
                         "{{config.items()}}"],
        },
        "ssrf_basic": {
            "name": "SSRF (Server-Side Request Forgery)",
            "patterns": ["http://localhost", "http://127.0.0.1", "http://169.254.169.254"],
            "payloads": ["http://127.0.0.1:80", "http://169.254.169.254/latest/meta-data/",
                         "file:///etc/passwd", "gopher://127.0.0.1:6379/_INFO"],
        },
        "idor_basic": {
            "name": "IDOR (Insecure Direct Object Reference)",
            "patterns": ["?id=", "?user=", "?doc=", "/api/"],
            "payloads": ["?id=1", "?id=0", "?id=-1", "?id=999", "?user=admin"],
        },
    },
    "crypto": {
        "base64_decode": {
            "name": "Base64 Decode",
            "detect": lambda d: _try_base64(d),
        },
        "caesar_brute": {
            "name": "Caesar Cipher Brute Force",
            "detect": lambda d: _caesar_brute(d),
        },
        "xor_single": {
            "name": "XOR Single Byte",
            "detect": lambda d: _xor_single_byte(d),
        },
        "hash_identify": {
            "name": "Hash Identification",
            "detect": lambda d: _identify_hash(d),
        },
        "hash_crack": {
            "name": "Hash Cracking (Rainbow Table + Dictionary)",
            "detect": lambda d: _crack_hash(d),
        },
        "rsa_basic": {
            "name": "RSA Basic Analysis",
            "detect": lambda d: _rsa_analyze(d),
        },
    },
    "reverse": {
        "strings_extract": {
            "name": "Strings Extraction",
            "detect": lambda d: _strings_extract(d),
        },
        "file_type": {
            "name": "File Type Identification",
            "detect": lambda d: _file_type(d),
        },
    },
    "forensic": {
        "file_carving": {
            "name": "File Carving (binwalk-style)",
            "detect": lambda d: _file_carving(d),
        },
        "strings_extract": {
            "name": "Strings Extraction",
            "detect": lambda d: _strings_extract(d),
        },
        "stego_basic": {
            "name": "Steganography Detection",
            "detect": lambda d: _stego_detect(d),
        },
    },
    "misc": {
        "encoding_detect": {
            "name": "Encoding Detection",
            "detect": lambda d: _detect_encoding(d),
        },
    },
}

# ─── Techniques Crypto ───

def _crack_hash(data: str) -> dict:
    """Cracke un hash via rainbow table + dictionnaire + règles."""
    import sys as _sys
    _sys.path.insert(0, "/home/aza/eva-adam-v2/wordlists")
    try:
        from rainbow_tool import crack_hash as _crack, identify_hash as _identify
    except ImportError:
        return {"success": False, "error": "rainbow_tool non disponible"}

    target = data.strip()
    # Auto-identifier
    candidates = _identify(target)
    if not candidates:
        return {"success": False, "error": "Hash non identifiable"}

    # Essayer chaque algorithme possible
    for algo in candidates:
        if algo in ("md5", "sha1", "sha256", "sha512"):
            result = _crack(target, algo)
            if result.get("cracked"):
                plaintext = result["plaintext"]
                # Vérifier si le plaintext contient un flag
                if _has_flag(plaintext):
                    return {"success": True, "decoded": plaintext, "flags": _extract_flags(plaintext),
                            "technique": "hash_crack", "algo": algo, "method": result.get("method")}
                # Le plaintext lui-même peut être le flag ou un indice
                return {"success": True, "decoded": plaintext, "plaintext": plaintext,
                        "technique": "hash_crack", "algo": algo, "method": result.get("method")}

    # Si rainbow + dictionnaire échoue, essayer avec règles
    for algo in candidates:
        if algo in ("md5", "sha1", "sha256", "sha512"):
            try:
                from rainbow_tool import crack_with_rules
                result = crack_with_rules(target, algo)
                if result.get("cracked"):
                    plaintext = result["plaintext"]
                    return {"success": True, "decoded": plaintext, "plaintext": plaintext,
                            "technique": "hash_crack", "algo": algo, "method": "rule_based"}
            except Exception:
                continue

    return {"success": False, "error": "Hash non cracké", "candidates": candidates}

def _try_base64(data: str) -> dict:
    """Tente de décoder du base64."""
    try:
        decoded = base64.b64decode(data, validate=True).decode("utf-8", errors="replace")
        if _has_flag(decoded):
            return {"success": True, "decoded": decoded, "technique": "base64_decode"}
        return {"success": True, "decoded": decoded, "technique": "base64_decode"}
    except Exception:
        return {"success": False}

def _caesar_brute(data: str) -> dict:
    """Brute force Caesar cipher."""
    for shift in range(26):
        result = ""
        for c in data:
            if c.isalpha():
                base = ord('A') if c.isupper() else ord('a')
                result += chr((ord(c) - base + shift) % 26 + base)
            else:
                result += c
        if _has_flag(result):
            return {"success": True, "shift": shift, "decoded": result, "technique": "caesar_brute"}
    return {"success": False}

def _xor_single_byte(data: str) -> dict:
    """XOR avec toutes les valeurs d'un octet."""
    try:
        raw = bytes.fromhex(data) if all(c in "0123456789abcdefABCDEF" for c in data) else data.encode()
    except Exception:
        raw = data.encode()
    for key in range(256):
        result = bytes([b ^ key for b in raw])
        try:
            decoded = result.decode("utf-8", errors="replace")
            if _has_flag(decoded):
                return {"success": True, "key": key, "decoded": decoded, "technique": "xor_single_byte"}
        except Exception:
            continue
    return {"success": False}

def _identify_hash(data: str) -> dict:
    """Identifie le type de hash."""
    data = data.strip()
    lengths = {32: "MD5", 40: "SHA1", 64: "SHA256", 128: "SHA512"}
    if len(data) in lengths and all(c in "0123456789abcdefABCDEF" for c in data):
        return {"success": True, "hash_type": lengths[len(data)], "hash": data, "technique": "hash_identify"}
    # bcrypt
    if data.startswith("$2"):
        return {"success": True, "hash_type": "bcrypt", "hash": data, "technique": "hash_identify"}
    return {"success": False}

def _rsa_analyze(data: str) -> dict:
    """Analyse basique RSA — cherche n, e, c dans le data."""
    nums = re.findall(r"\d+", data)
    if len(nums) >= 3:
        return {
            "success": True,
            "technique": "rsa_basic",
            "n": nums[-3] if len(nums) >= 3 else None,
            "e": nums[-2] if len(nums) >= 2 else None,
            "c": nums[-1] if nums else None,
            "note": "Vérifier si n est factorisable (factordb, small primes)",
        }
    return {"success": False}

# ─── Techniques Reverse/Forensic ───

def _strings_extract(data: str) -> dict:
    """Extrait les strings d'un fichier ou texte."""
    path = data.strip()
    if os.path.isfile(path):
        try:
            r = subprocess.run(["strings", path], capture_output=True, text=True, timeout=10)
            strings_found = r.stdout.split("\n") if r.returncode == 0 else []
        except Exception:
            strings_found = []
    else:
        # Extract printable strings from raw data
        strings_found = re.findall(r"[\x20-\x7e]{4,}", data)
    flags = [s for s in strings_found if _has_flag(s)]
    if flags:
        return {"success": True, "flags": flags, "technique": "strings_extract"}
    return {"success": True, "strings": strings_found[:50], "technique": "strings_extract"}

def _file_type(data: str) -> dict:
    """Identifie le type de fichier."""
    path = data.strip()
    if os.path.isfile(path):
        try:
            r = subprocess.run(["file", path], capture_output=True, text=True, timeout=5)
            return {"success": True, "file_info": r.stdout.strip(), "technique": "file_type"}
        except Exception:
            pass
    return {"success": False}

def _file_carving(data: str) -> dict:
    """Cherche des fichiers cachés (binwalk-style)."""
    path = data.strip()
    if not os.path.isfile(path):
        return {"success": False}
    # Magic bytes communs
    magic = {
        b"\x89PNG": "PNG image",
        b"\xff\xd8\xff": "JPEG image",
        b"PK\x03\x04": "ZIP archive",
        b"\x1f\x8b": "GZIP data",
        b"BM": "BMP image",
        b"%PDF": "PDF document",
        b"\x7fELF": "ELF binary",
        b"MZ": "Windows PE",
    }
    try:
        with open(path, "rb") as f:
            content = f.read()
        findings = []
        for sig, desc in magic.items():
            pos = 0
            while True:
                pos = content.find(sig, pos)
                if pos == -1:
                    break
                findings.append({"offset": pos, "type": desc})
                pos += 1
        # Search for flags in binary
        flags = []
        for s in re.findall(rb"[\x20-\x7e]{4,}", content):
            try:
                decoded = s.decode("ascii")
                if _has_flag(decoded):
                    flags.append(decoded)
            except Exception:
                continue
        return {"success": True, "findings": findings, "flags": flags, "technique": "file_carving"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def _stego_detect(data: str) -> dict:
    """Détection stéganographique basique."""
    path = data.strip()
    if not os.path.isfile(path):
        return {"success": False}
    try:
        with open(path, "rb") as f:
            content = f.read()
        # Check for appended data after PNG IEND
        if content[:4] == b"\x89PNG":
            iend_pos = content.find(b"IEND")
            if iend_pos > 0 and len(content) > iend_pos + 8:
                appended = content[iend_pos + 8:]
                if appended:
                    flags = []
                    for pat in FLAG_PATTERNS:
                        m = re.search(pat.pattern, appended.decode("ascii", errors="replace"))
                        if m:
                            flags.append(m.group(0))
                    return {"success": True, "appended_data": len(appended), "flags": flags, "technique": "stego_detect"}
        # Check for appended data after JPEG EOI
        if content[:2] == b"\xff\xd8":
            eoi_pos = content.rfind(b"\xff\xd9")
            if eoi_pos > 0 and len(content) > eoi_pos + 2:
                appended = content[eoi_pos + 2:]
                if appended:
                    flags = []
                    for pat in FLAG_PATTERNS:
                        m = re.search(pat.pattern, appended.decode("ascii", errors="replace"))
                        if m:
                            flags.append(m.group(0))
                    return {"success": True, "appended_data": len(appended), "flags": flags, "technique": "stego_detect"}
        return {"success": True, "note": "No appended data found", "technique": "stego_detect"}
    except Exception as e:
        return {"success": False, "error": str(e)}

# ─── Techniques Misc ───

def _detect_encoding(data: str) -> dict:
    """Détecte l'encodage d'une string."""
    data = data.strip()
    # Base64
    try:
        decoded = base64.b64decode(data, validate=True)
        if all(b < 128 for b in decoded):
            text = decoded.decode("ascii", errors="replace")
            if _has_flag(text):
                return {"success": True, "encoding": "base64", "decoded": text, "technique": "encoding_detect"}
            return {"success": True, "encoding": "base64", "decoded": text, "technique": "encoding_detect"}
    except Exception:
        pass
    # Hex
    if all(c in "0123456789abcdefABCDEF" for c in data) and len(data) % 2 == 0:
        try:
            decoded = bytes.fromhex(data).decode("utf-8", errors="replace")
            if _has_flag(decoded):
                return {"success": True, "encoding": "hex", "decoded": decoded, "technique": "encoding_detect"}
            return {"success": True, "encoding": "hex", "decoded": decoded, "technique": "encoding_detect"}
        except Exception:
            pass
    # ROT13
    import codecs
    rot13 = codecs.decode(data, "rot_13")
    if _has_flag(rot13):
        return {"success": True, "encoding": "rot13", "decoded": rot13, "technique": "encoding_detect"}
    # Binary
    if all(c in "01 " for c in data):
        try:
            decoded = "".join(chr(int(data.replace(" ", "")[i:i+8], 2)) for i in range(0, len(data.replace(" ", "")), 8))
            if _has_flag(decoded):
                return {"success": True, "encoding": "binary", "decoded": decoded, "technique": "encoding_detect"}
            return {"success": True, "encoding": "binary", "decoded": decoded, "technique": "encoding_detect"}
        except Exception:
            pass
    return {"success": False}

# ─── Helpers ───

def _has_flag(text: str) -> bool:
    return any(p.search(text) for p in FLAG_PATTERNS)

def _extract_flags(text: str) -> list:
    flags = []
    for p in FLAG_PATTERNS:
        flags.extend(p.findall(text))
    return flags

# ─── Solver ───

def solve_challenge(challenge: dict) -> dict:
    """
    Tente de résoudre un challenge CTF.
    challenge = {
        "id": str,
        "category": "web|crypto|reverse|pwn|forensic|misc",
        "data": str,      # Données du challenge (texte, chemin fichier, URL, etc.)
        "hint": str,      # Indice optionnel
        "url": str,       # URL optionnelle
    }
    """
    cat = challenge.get("category", "misc")
    data = challenge.get("data", "")
    challenge_id = challenge.get("id", "unknown")
    hint = challenge.get("hint", "")

    log(f"Résolution challenge #{challenge_id} [{cat}] — data={data[:80]}...")

    # 1. Recherche RAG pour techniques similaires
    rag_results = rag_search(f"CTF {cat} {hint} {data[:100]}", n=3)
    if rag_results:
        log(f"  RAG: {len(rag_results)} résultat(s) pertinent(s)")

    # 2. Appliquer les techniques de la catégorie
    techniques = TECHNIQUES.get(cat, {})
    results = []

    for tech_name, tech_def in techniques.items():
        if "detect" in tech_def:
            # Crypto/forensic/reverse: fonction de détection
            result = tech_def["detect"](data)
            if result.get("success"):
                result["technique_name"] = tech_def["name"]
                results.append(result)
                # Pour le hash cracking, le plaintext EST la solution
                if tech_name == "hash_crack" and result.get("plaintext"):
                    plaintext = result["plaintext"]
                    flags = _extract_flags(plaintext)
                    if flags:
                        log(f"  ✅ FLAG trouvé via {tech_name}!")
                        return {
                            "solved": True,
                            "challenge_id": challenge_id,
                            "category": cat,
                            "technique": tech_name,
                            "result": result,
                            "flags": flags,
                        }
                    # Le plaintext cracké est considéré comme la solution
                    log(f"  ✅ Hash cracké via {tech_name}: {plaintext}")
                    return {
                        "solved": True,
                        "challenge_id": challenge_id,
                        "category": cat,
                        "technique": tech_name,
                        "result": result,
                        "flags": [f"flag{{{plaintext}}}"],
                    }
                if _has_flag(result.get("decoded", "")) or result.get("flags"):
                    log(f"  ✅ FLAG trouvé via {tech_name}!")
                    return {
                        "solved": True,
                        "challenge_id": challenge_id,
                        "category": cat,
                        "technique": tech_name,
                        "result": result,
                        "flags": result.get("flags", _extract_flags(result.get("decoded", ""))),
                    }
        elif "payloads" in tech_def:
            # Web: tester les payloads
            for payload in tech_def["payloads"]:
                # Pour les challenges web, on simule l'injection
                # (en mode standalone, on cherche des patterns dans le data)
                if payload.lower() in data.lower():
                    results.append({
                        "technique": tech_name,
                        "technique_name": tech_def["name"],
                        "matched_payload": payload,
                        "success": True,
                    })
                    log(f"  ✅ Pattern web détecté via {tech_name}: {payload}")

    # 3. Si aucune technique ne trouve un flag, essayer misc (encoding)
    if not any(r.get("success") for r in results):
        for tech_name, tech_def in TECHNIQUES.get("misc", {}).items():
            result = tech_def["detect"](data)
            if result.get("success"):
                result["technique_name"] = tech_def["name"]
                results.append(result)
                if _has_flag(result.get("decoded", "")):
                    log(f"  ✅ FLAG trouvé via {tech_name} (misc)!")
                    return {
                        "solved": True,
                        "challenge_id": challenge_id,
                        "category": cat,
                        "technique": tech_name,
                        "result": result,
                        "flags": _extract_flags(result.get("decoded", "")),
                    }

    # 4. Check si un résultat contient un flag sans qu'on l'ait détecté
    for r in results:
        decoded = r.get("decoded", "")
        flags = _extract_flags(decoded)
        if flags:
            log(f"  ✅ FLAG trouvé dans résultat {r.get('technique', 'unknown')}!")
            return {
                "solved": True,
                "challenge_id": challenge_id,
                "category": cat,
                "technique": r.get("technique", "unknown"),
                "result": r,
                "flags": flags,
            }

    # 5. Non résolu — publier pour apprentissage
    log(f"  ❌ Challenge #{challenge_id} non résolu — {len(results)} technique(s) essayée(s)")
    return {
        "solved": False,
        "challenge_id": challenge_id,
        "category": cat,
        "techniques_tried": [r.get("technique", r.get("technique_name", "unknown")) for r in results],
        "results": results,
    }

# ─── Apprentissage ───

def save_solution(challenge: dict, solution: dict):
    """Sauvegarde la solution dans un fichier + publie l'apprentissage."""
    challenge_id = challenge.get("id", "unknown")
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    solution_file = SOLUTIONS_DIR / f"{challenge_id}_{ts}.json"

    solution_data = {
        "challenge": challenge,
        "solution": solution,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent": AGENT_ID,
    }

    with open(solution_file, "w") as f:
        json.dump(solution_data, f, indent=2, ensure_ascii=False)

    log(f"  Solution sauvegardée: {solution_file}")

    # Publier l'apprentissage sur le bus
    publish("ctf:learning", {
        "challenge_id": challenge_id,
        "category": challenge.get("category"),
        "solved": solution.get("solved"),
        "technique": solution.get("technique"),
        "flags": solution.get("flags", []),
        "techniques_tried": solution.get("techniques_tried", []),
        "solution_file": str(solution_file),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }, priority=3)

    # Publier aussi sur evolution:code_review pour que evolution apprenne
    if solution.get("solved"):
        publish("evolution:code_review", {
            "type": "ctf_solution",
            "rule_id": f"ctf-{challenge.get('category')}-{solution.get('technique')}",
            "pattern": f"CTF {challenge.get('category')} → {solution.get('technique')}",
            "strategie": solution.get("technique"),
            "fitness_score": 1.0 if solution.get("solved") else 0.0,
            "source_event": "ctf:learning",
            "canal_origine": "ctf",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }, priority=3)

def load_challenges() -> list:
    """Charge les challenges depuis le répertoire local."""
    challenges = []
    for f in CHALLENGE_DIR.glob("*.json"):
        try:
            with open(f) as fh:
                data = json.load(fh)
                if isinstance(data, list):
                    challenges.extend(data)
                elif isinstance(data, dict):
                    challenges.append(data)
        except Exception as e:
            log(f"Erreur chargement {f}: {e}", "WARN")
    return challenges

# ─── Challenges intégrés ───

BUILTIN_CHALLENGES = [
    # Crypto — Base64
    {"id": "b64-001", "category": "crypto", "data": "ZmxhZ3tjYV9wYWdlX2VzdF9jb29sfQ==", "hint": "base64"},
    # Crypto — Caesar
    {"id": "caesar-001", "category": "crypto", "data": "synt{pnrfne_fvggenesyo}", "hint": "caesar shift 13"},
    # Crypto — XOR hex
    {"id": "xor-001", "category": "crypto", "data": "666c61677b786f725f31735f676f6f647d", "hint": "XOR single byte"},
    # Misc — Hex
    {"id": "hex-001", "category": "misc", "data": "666c61677b6865785f656e636f64696e677d", "hint": "hex encoding"},
    # Misc — Binary
    {"id": "bin-001", "category": "misc",
     "data": "01100110 01101100 01100001 01100111 01111011 01100010 01101001 01101110 01100001 01110010 01111001 01111101",
     "hint": "binary encoding"},
    # Crypto — Hash identification
    {"id": "hash-001", "category": "crypto", "data": "5d41402abc4b2a76b9719d911017c592", "hint": "identify this hash"},
    # Crypto — Hash cracking (rainbow table)
    {"id": "hash-002", "category": "crypto", "data": "42f749ade7f9e195bf475f37a44cafcb", "hint": "crack this md5 hash"},
    # Crypto — Hash SHA1 cracking
    {"id": "hash-003", "category": "crypto", "data": "aaf4c61ddcc5e8a2dabede0f3b482cd9aea9434d", "hint": "crack this sha1 hash"},
    # Misc — ROT13
    {"id": "rot13-001", "category": "misc", "data": "synt{ebg13_favcele}", "hint": "ROT13"},
    # Crypto — Base64 + flag
    {"id": "b64-002", "category": "crypto", "data": "ZmxhZ3tiYXNlNjRfZGVjb2Rpbmd9", "hint": "base64"},
]

# ─── Boucle principale ───

def run_training(challenges: list = None, loop: bool = False, interval: int = 60):
    """Entraîne adam-ctf sur une série de challenges."""
    if challenges is None:
        challenges = load_challenges()
    if not challenges:
        log("Aucun challenge local — utilisation des challenges intégrés")
        challenges = BUILTIN_CHALLENGES

    log(f"=== ADAM-CTF — {len(challenges)} challenge(s) à résoudre ===")

    while True:
        solved_count = 0
        total = len(challenges)

        for i, challenge in enumerate(challenges):
            log(f"\n--- Challenge {i+1}/{total}: #{challenge.get('id')} [{challenge.get('category')}] ---")
            heartbeat()

            solution = solve_challenge(challenge)
            save_solution(challenge, solution)

            if solution.get("solved"):
                solved_count += 1
                publish("ctf:solved", {
                    "challenge_id": challenge.get("id"),
                    "category": challenge.get("category"),
                    "technique": solution.get("technique"),
                    "flags": solution.get("flags", []),
                }, priority=2)
            else:
                publish("ctf:failed", {
                    "challenge_id": challenge.get("id"),
                    "category": challenge.get("category"),
                    "techniques_tried": solution.get("techniques_tried", []),
                }, priority=2)

            time.sleep(1)

        log(f"\n=== Bilan: {solved_count}/{total} résolus ({100*solved_count//total}%) ===")

        # Publier le bilan
        publish("ctf:training_complete", {
            "total": total,
            "solved": solved_count,
            "success_rate": f"{100*solved_count//total}%" if total else "0%",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }, priority=2)

        if not loop:
            break
        log(f"Prochaine itération dans {interval}s...")
        time.sleep(interval)

def register_agent():
    """Enregistre l'agent dans la DB."""
    conn = db_conn()
    now = datetime.now(timezone.utc).isoformat()
    conn.execute("""
        INSERT OR IGNORE INTO agents (agent_id, display_name, status, heartbeat_at, config)
        VALUES (?, ?, 'idle', ?, ?)
    """, (AGENT_ID, DISPLAY_NAME, now, json.dumps({
        "timeout": 300, "retries": 1,
        "categories": ["web", "crypto", "reverse", "pwn", "forensic", "misc"],
    })))
    conn.commit()

    # Subscriptions
    subs = [
        ("ctf:challenge", "/home/aza/scripts/adam-ctf.py", 1),
        ("ctf:new_challenge", "/home/aza/scripts/adam-ctf.py", 1),
    ]
    for channel, handler, enabled in subs:
        conn.execute("""
            INSERT OR IGNORE INTO subscriptions (agent_id, channel, handler, enabled)
            VALUES (?, ?, ?, ?)
        """, (AGENT_ID, channel, handler, enabled))
    conn.commit()
    conn.close()
    log(f"Agent {AGENT_ID} enregistré dans la DB")

# ─── CLI ───

def main():
    parser = argparse.ArgumentParser(description="ADAM-CTF — Entraînement CTF autonome")
    parser.add_argument("--phase", choices=["train", "register", "solve"], default="train",
                        help="Phase: train (défaut), register, solve (challenge unique)")
    parser.add_argument("--loop", action="store_true", help="Boucle continue")
    parser.add_argument("--interval", type=int, default=300, help="Intervalle entre les itérations (s)")
    parser.add_argument("--category", choices=["web", "crypto", "reverse", "pwn", "forensic", "misc"],
                        help="Filtrer par catégorie")
    parser.add_argument("--data", type=str, help="Données du challenge (pour --phase solve)")
    parser.add_argument("--hint", type=str, help="Indice (pour --phase solve)")
    args = parser.parse_args()

    if args.phase == "register":
        register_agent()
        return

    if args.phase == "solve":
        challenge = {
            "id": "cli-001",
            "category": args.category or "misc",
            "data": args.data or "",
            "hint": args.hint or "",
        }
        solution = solve_challenge(challenge)
        save_solution(challenge, solution)
        print(json.dumps(solution, indent=2, ensure_ascii=False))
        return

    # Train (défaut)
    register_agent()
    challenges = BUILTIN_CHALLENGES
    if args.category:
        challenges = [c for c in challenges if c.get("category") == args.category]
    run_training(challenges=challenges, loop=args.loop, interval=args.interval)

if __name__ == "__main__":
    main()
