#!/usr/bin/env python3
"""
Rainbow Table Generator & Hash Cracker pour adam-ctf.

Génère des rainbow tables pour MD5, SHA1, SHA256 à partir de wordlists.
Cracke des hashes par lookup direct dans les rainbow tables ou par attaque
dictionnaire en temps réel.

Usage:
  python3.13 rainbow_tool.py --generate --algo md5 --wordlist rockyou.txt
  python3.13 rainbow_tool.py --crack 5d41402abc4b2a76b9719d911017c592
  python3.13 rainbow_tool.py --crack 5d41402abc4b2a76b9719d911017c592 --algo md5
  python3.13 rainbow_tool.py --identify 5d41402abc4b2a76b9719d911017c592
"""

import argparse
import hashlib
import json
import os
import sqlite3
import sys
import time
from pathlib import Path
from datetime import datetime, timezone

# ─── Config ───
WORDLIST_DIR = Path("/home/aza/eva-adam-v2/wordlists")
RAG_DB = Path("/home/aza/eva-adam-v2/wordlists/rainbow-tables/rainbow.db")

ALGORITHMS = {
    "md5":    hashlib.md5,
    "sha1":   hashlib.sha1,
    "sha256": hashlib.sha256,
    "sha512": hashlib.sha512,
}

# Longueurs de hash pour identification automatique
HASH_LENGTHS = {
    32: "md5",
    40: "sha1",
    64: "sha256",
    128: "sha512",
}

# Wordlists par ordre de priorité (plus petit = plus rapide à parcourir)
DEFAULT_WORDLISTS = [
    WORDLIST_DIR / "dictionaries/ctf/500_worst.txt",
    WORDLIST_DIR / "dictionaries/ctf/best105.txt",
    WORDLIST_DIR / "dictionaries/ctf/common_win.txt",
    WORDLIST_DIR / "leaked/seclists/top10k_common.txt",
    WORDLIST_DIR / "leaked/seclists/100k-ncsc.txt",
    WORDLIST_DIR / "leaked/seclists/pwdb_top1M.txt",
    WORDLIST_DIR / "leaked/rockyou/rockyou.txt",
]

def get_rainbow_conn():
    """Ouvre/crée la DB SQLite des rainbow tables."""
    RAG_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(RAG_DB))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS rainbow (
            algo TEXT NOT NULL,
            hash TEXT NOT NULL,
            plaintext TEXT NOT NULL,
            PRIMARY KEY (algo, hash)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_rainbow_hash ON rainbow(algo, hash)")
    conn.commit()
    return conn

def identify_hash(h: str) -> list:
    """Identifie les algorithmes possibles pour un hash."""
    h = h.strip()
    possible = []
    if len(h) in HASH_LENGTHS:
        if all(c in "0123456789abcdefABCDEF" for c in h):
            possible.append(HASH_LENGTHS[len(h)])
    # bcrypt
    if h.startswith("$2a$") or h.startswith("$2b$") or h.startswith("$2y$"):
        possible.append("bcrypt")
    # argon2
    if h.startswith("$argon2"):
        possible.append("argon2")
    # NTLM (16 bytes = 32 hex chars, même que md5 mais format Windows)
    if len(h) == 32 and all(c in "0123456789abcdefABCDEF" for c in h):
        possible.append("ntlm")
    return possible

def generate_rainbow(algo: str, wordlist_path: str, verbose: bool = True):
    """Génère une rainbow table pour un algorithme donné."""
    if algo not in ALGORITHMS:
        print(f"Algorithme non supporté: {algo}")
        return 0

    hash_func = ALGORITHMS[algo]
    conn = get_rainbow_conn()

    count = 0
    batch = []
    batch_size = 5000
    t0 = time.time()

    with open(wordlist_path, "r", errors="ignore") as f:
        for i, line in enumerate(f):
            word = line.strip()
            if not word:
                continue
            h = hash_func(word.encode()).hexdigest()
            batch.append((algo, h, word))

            if len(batch) >= batch_size:
                conn.executemany("INSERT OR IGNORE INTO rainbow VALUES (?,?,?)", batch)
                conn.commit()
                count += len(batch)
                batch = []
                if verbose and (count % 100000 == 0):
                    elapsed = time.time() - t0
                    print(f"  {algo}: {count:,} entrées ({count/elapsed:.0f}/s)")

    if batch:
        conn.executemany("INSERT OR IGNORE INTO rainbow VALUES (?,?,?)", batch)
        conn.commit()
        count += len(batch)

    elapsed = time.time() - t0
    print(f"✅ {algo}: {count:,} entrées générées en {elapsed:.1f}s depuis {wordlist_path}")
    conn.close()
    return count

def crack_hash(target_hash: str, algo: str = None, use_rainbow: bool = True) -> dict:
    """
    Tente de cracker un hash.
    1. Lookup dans la rainbow table (si générée)
    2. Attaque dictionnaire en temps réel (si rainbow échoue)
    """
    target_hash = target_hash.strip().lower()

    # Auto-identifier l'algorithme si non spécifié
    if not algo:
        candidates = identify_hash(target_hash)
        if not candidates:
            return {"cracked": False, "error": "Hash non identifiable"}
        # Tester chaque candidat
        for cand in candidates:
            if cand in ALGORITHMS:
                result = crack_hash(target_hash, cand, use_rainbow)
                if result.get("cracked"):
                    return result
        return {"cracked": False, "error": f"Pas trouvé avec: {candidates}"}

    # Si c'est bcrypt/argon2, on ne peut pas utiliser rainbow table
    if algo in ("bcrypt", "argon2"):
        return {"cracked": False, "error": f"{algo} non supporté par rainbow table (trop lent)"}

    # 1. Lookup rainbow table
    if use_rainbow:
        conn = get_rainbow_conn()
        row = conn.execute(
            "SELECT plaintext FROM rainbow WHERE algo=? AND hash=?",
            (algo, target_hash)
        ).fetchone()
        conn.close()
        if row:
            return {
                "cracked": True,
                "hash": target_hash,
                "algo": algo,
                "plaintext": row[0],
                "method": "rainbow_table",
            }

    # 2. Attaque dictionnaire en temps réel
    if algo not in ALGORITHMS:
        return {"cracked": False, "error": f"Algorithme {algo} non supporté"}

    hash_func = ALGORITHMS[algo]
    t0 = time.time()
    words_tried = 0

    for wl_path in DEFAULT_WORDLISTS:
        if not wl_path.exists():
            continue
        with open(wl_path, "r", errors="ignore") as f:
            for line in f:
                word = line.strip()
                if not word:
                    continue
                words_tried += 1
                h = hash_func(word.encode()).hexdigest()
                if h == target_hash:
                    elapsed = time.time() - t0
                    # Sauvegarder dans la rainbow table pour les prochaines fois
                    conn = get_rainbow_conn()
                    conn.execute("INSERT OR IGNORE INTO rainbow VALUES (?,?,?)", (algo, h, word))
                    conn.commit()
                    conn.close()
                    return {
                        "cracked": True,
                        "hash": target_hash,
                        "algo": algo,
                        "plaintext": word,
                        "method": "dictionary",
                        "words_tried": words_tried,
                        "time": f"{elapsed:.2f}s",
                    }

    elapsed = time.time() - t0
    return {
        "cracked": False,
        "hash": target_hash,
        "algo": algo,
        "words_tried": words_tried,
        "time": f"{elapsed:.2f}s",
        "error": "Pas trouvé dans les wordlists",
    }

def crack_with_rules(target_hash: str, algo: str = None, max_rules: int = 1000) -> dict:
    """
    Crackage avec règles simples (ajout de chiffres, leetspeak, etc.)
    quand le dictionnaire de base échoue.
    """
    # D'abord essayer sans règles
    result = crack_hash(target_hash, algo)
    if result.get("cracked"):
        return result

    # Si échec, appliquer des règles de mutation
    if not algo or algo not in ALGORITHMS:
        return result

    hash_func = ALGORITHMS[algo]
    target_hash = target_hash.strip().lower()

    # Mots de base à muter (top 1000 des passwords communs)
    base_words = []
    for wl_path in DEFAULT_WORDLISTS[:4]:
        if wl_path.exists():
            with open(wl_path, "r", errors="ignore") as f:
                base_words = [line.strip() for line in f if line.strip()][:1000]
            break

    rules = [
        lambda w: w + "1",      # suffix 1
        lambda w: w + "123",    # suffix 123
        lambda w: w + "!",      # suffix !
        lambda w: w + "2024",   # suffix year
        lambda w: w + "2025",
        lambda w: w + "2026",
        lambda w: w.capitalize(),
        lambda w: w.upper(),
        lambda w: w[::-1],      # reverse
        lambda w: w.replace("a", "@").replace("o", "0").replace("e", "3").replace("i", "1"),
        lambda w: w + w[-1],    # double last char
        lambda w: "!" + w,      # prefix !
        lambda w: w[:1].upper() + w[1:] + "1",
    ]

    count = 0
    for word in base_words:
        for rule in rules:
            if count >= max_rules * len(base_words):
                break
            mutated = rule(word)
            count += 1
            h = hash_func(mutated.encode()).hexdigest()
            if h == target_hash:
                return {
                    "cracked": True,
                    "hash": target_hash,
                    "algo": algo,
                    "plaintext": mutated,
                    "method": "rule_based",
                    "rules_tried": count,
                    "base_word": word,
                }

    return {
        "cracked": False,
        "hash": target_hash,
        "algo": algo,
        "rules_tried": count,
        "error": "Pas trouvé avec règles",
    }

def stats():
    """Affiche les statistiques des rainbow tables."""
    conn = get_rainbow_conn()
    rows = conn.execute("""
        SELECT algo, COUNT(*) as count FROM rainbow GROUP BY algo ORDER BY count DESC
    """).fetchall()
    total = 0
    print("Rainbow Tables — Statistiques:")
    print(f"  DB: {RAG_DB}")
    print(f"  Size: {os.path.getsize(RAG_DB) / 1024 / 1024:.1f} MB")
    print()
    for algo, count in rows:
        print(f"  {algo:8s}: {count:>12,} entrées")
        total += count
    print(f"  {'TOTAL':8s}: {total:>12,} entrées")
    conn.close()

# ─── CLI ───

def main():
    parser = argparse.ArgumentParser(description="Rainbow Table Generator & Hash Cracker")
    parser.add_argument("--generate", action="store_true", help="Génère les rainbow tables")
    parser.add_argument("--crack", type=str, help="Hash à cracker")
    parser.add_argument("--identify", type=str, help="Identifier un hash")
    parser.add_argument("--algo", choices=list(ALGORITHMS.keys()), help="Algorithme")
    parser.add_argument("--wordlist", type=str, help="Wordlist spécifique (pour --generate)")
    parser.add_argument("--rules", action="store_true", help="Utiliser règles de mutation")
    parser.add_argument("--stats", action="store_true", help="Statistiques rainbow tables")
    args = parser.parse_args()

    if args.stats:
        stats()
        return

    if args.identify:
        candidates = identify_hash(args.identify)
        print(f"Hash: {args.identify}")
        print(f"Algorithme(s) possible(s): {candidates or 'non identifiable'}")
        return

    if args.generate:
        wordlists_to_use = []
        if args.wordlist:
            wordlists_to_use = [(args.wordlist, args.algo or "md5")]
        else:
            # Générer pour tous les algos avec les wordlists les plus utiles
            wl_priority = [
                WORDLIST_DIR / "leaked/seclists/top10k_common.txt",
                WORDLIST_DIR / "leaked/seclists/100k-ncsc.txt",
            ]
            algos = [args.algo] if args.algo else list(ALGORITHMS.keys())
            for algo in algos:
                for wl in wl_priority:
                    if wl.exists():
                        wordlists_to_use.append((str(wl), algo))

        for wl_path, algo in wordlists_to_use:
            if not os.path.exists(wl_path):
                print(f"⚠ Wordlist introuvable: {wl_path}")
                continue
            generate_rainbow(algo, wl_path)
        stats()
        return

    if args.crack:
        if args.rules:
            result = crack_with_rules(args.crack, args.algo)
        else:
            result = crack_hash(args.crack, args.algo)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return

    parser.print_help()

if __name__ == "__main__":
    main()
