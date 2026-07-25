#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ADAM-CHAT — Modèles de base de données et chiffrement AES-256-GCM

Migration Go Bus: les événements chat (message_sent, user_joined, etc.) sont
publiés sur le Go Bus (http://localhost:8086/api/publish) en plus d'être
stockés dans la DB locale chat.db.
"""

import os
import json
import base64
import hashlib
import sqlite3
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Optional

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

# ─── Go Bus ───────────────────────────────────────────────────────

GO_BUS_URL = "http://localhost:8086/api/publish"


def publish_to_bus(topic: str, payload: dict, source: str = "adam-chat", priority: int = 5):
    """Publie un événement sur le Go Bus via HTTP."""
    try:
        body = json.dumps({
            "topic": topic,
            "source": source,
            "priority": priority,
            "payload": payload,
        }).encode()
        req = urllib.request.Request(
            GO_BUS_URL, data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=5)
    except Exception:
        # Le bus est best-effort — on ne bloque jamais le chat
        pass


# ─── Chiffrement AES-256-GCM ───────────────────────────────────────

def derive_key(password: str, salt: bytes = None) -> tuple[bytes, bytes]:
    """Dérive une clé AES-256 à partir d'un mot de passe via PBKDF2."""
    if salt is None:
        salt = os.urandom(32)
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=600_000,
    )
    key = kdf.derive(password.encode('utf-8'))
    return key, salt


def encrypt_message(plaintext: str, key: bytes) -> str:
    """Chiffre un message avec AES-256-GCM. Retourne base64(salt + nonce + ciphertext)."""
    salt = os.urandom(32)
    nonce = os.urandom(12)
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode('utf-8'), None)
    payload = salt + nonce + ciphertext
    return base64.b64encode(payload).decode('utf-8')


def decrypt_message(encrypted: str, password: str) -> Optional[str]:
    """Déchiffre un message. encrypted = base64(salt + nonce + ciphertext)."""
    try:
        payload = base64.b64decode(encrypted)
        salt = payload[:32]
        nonce = payload[32:44]
        ciphertext = payload[44:]
        key, _ = derive_key(password, salt)
        aesgcm = AESGCM(key)
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        return plaintext.decode('utf-8')
    except Exception:
        return None


def decrypt_message_with_key(encrypted: str, key: bytes) -> Optional[str]:
    """Déchiffre avec une clé déjà dérivée (plus rapide pour les lectures batch)."""
    try:
        payload = base64.b64decode(encrypted)
        salt = payload[:32]
        nonce = payload[32:44]
        ciphertext = payload[44:]
        # La clé est déjà dérivée, on saute PBKDF2
        # Re-dériver serait trop lent, on stocke la clé en session
        aesgcm = AESGCM(key)
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        return plaintext.decode('utf-8')
    except Exception:
        return None


# ─── Base de données ───────────────────────────────────────────────

DB_PATH = os.path.expanduser("~/chat/chat.db")


def get_db() -> sqlite3.Connection:
    """Retourne une connexion SQLite avec row_factory."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Crée les tables si elles n'existent pas."""
    conn = get_db()
    cur = conn.cursor()

    cur.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            display_name TEXT DEFAULT '',
            avatar_url TEXT DEFAULT '',
            public_key TEXT DEFAULT '',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            last_seen TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            description TEXT DEFAULT '',
            created_by INTEGER REFERENCES users(id),
            is_encrypted INTEGER DEFAULT 1,
            is_private INTEGER DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_id INTEGER NOT NULL REFERENCES channels(id),
            user_id INTEGER NOT NULL REFERENCES users(id),
            content TEXT NOT NULL,
            content_type TEXT DEFAULT 'text',
            file_url TEXT DEFAULT '',
            is_edited INTEGER DEFAULT 0,
            is_deleted INTEGER DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            edited_at TEXT DEFAULT NULL
        );

        CREATE TABLE IF NOT EXISTS channel_members (
            channel_id INTEGER NOT NULL REFERENCES channels(id),
            user_id INTEGER NOT NULL REFERENCES users(id),
            role TEXT DEFAULT 'member',
            joined_at TEXT NOT NULL DEFAULT (datetime('now')),
            PRIMARY KEY (channel_id, user_id)
        );

        CREATE TABLE IF NOT EXISTS sessions (
            token TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id),
            encryption_key TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            expires_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_messages_channel ON messages(channel_id, created_at);
        CREATE INDEX IF NOT EXISTS idx_messages_user ON messages(user_id);
        CREATE INDEX IF NOT EXISTS idx_sessions_expires ON sessions(expires_at);
    """)

    conn.commit()
    conn.close()

    # Notifier le Go Bus que le chat est initialisé
    publish_to_bus("chat:initialized", {
        "db_path": DB_PATH,
        "timestamp": now_iso(),
    })


# ─── Helpers ───────────────────────────────────────────────────────

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def seed_default_channels():
    """Crée les canaux par défaut si la table est vide."""
    conn = get_db()
    count = conn.execute("SELECT COUNT(*) FROM channels").fetchone()[0]
    if count == 0:
        channels = [
            ("general", "Canal général — discussions libres", 0),
            ("eva", "Canal EVA — discute avec l'assistant IA", 0),
            ("adam", "Canal ADAM — développement et code", 0),
            ("cybersec", "Canal CyberSécurité — veille et exploits", 0),
            ("dev", "Canal Développement — projets et techniques", 0),
        ]
        for name, desc, private in channels:
            conn.execute(
                "INSERT INTO channels (name, description, created_by, is_private) VALUES (?, ?, 1, ?)",
                (name, desc, private)
            )
            # Publier la création du canal sur le Go Bus
            publish_to_bus("chat:channel_created", {
                "name": name,
                "description": desc,
                "is_private": private,
            })
        # Ajouter tous les users existants aux nouveaux canaux
        for ch in conn.execute("SELECT id, name FROM channels").fetchall():
            for u in conn.execute("SELECT id, username FROM users").fetchall():
                conn.execute(
                    "INSERT OR IGNORE INTO channel_members (channel_id, user_id, role) VALUES (?, ?, ?)",
                    (ch['id'], u['id'], 'admin' if u['id'] == 1 else 'member')
                )
                publish_to_bus("chat:user_joined", {
                    "channel": ch['name'],
                    "username": u['username'],
                    "role": 'admin' if u['id'] == 1 else 'member',
                })
        conn.commit()
    conn.close()


def seed_admin():
    """Crée l'utilisateur admin par défaut si pas d'utilisateurs."""
    import bcrypt
    conn = get_db()
    count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if count == 0:
        pw_hash = bcrypt.hashpw(b"admin123", bcrypt.gensalt()).decode('utf-8')
        conn.execute(
            "INSERT INTO users (username, password_hash, display_name) VALUES (?, ?, ?)",
            ("admin", pw_hash, "Administrateur")
        )
        # Ajouter admin à tous les canaux
        for ch in conn.execute("SELECT id, name FROM channels").fetchall():
            conn.execute(
                "INSERT OR IGNORE INTO channel_members (channel_id, user_id, role) VALUES (?, ?, ?)",
                (ch['id'], 1, 'admin')
            )
        conn.commit()
        print("[✓] Compte admin créé : admin / admin123")

        # Publier l'événement sur le Go Bus
        publish_to_bus("chat:user_registered", {
            "username": "admin",
            "display_name": "Administrateur",
            "is_admin": True,
        })
    conn.close()
