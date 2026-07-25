#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ADAM-CHAT — Pont EVA
Relie le canal #eva à l'assistant EVA via hermes CLI
"""

import os
import sys
import json
import time
import subprocess
import sqlite3
import signal
import logging
from datetime import datetime, timezone

# Ajouter le répertoire courant au path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from models import get_db, derive_key, encrypt_message, decrypt_message
import base64

# ─── Configuration ─────────────────────────────────────────────────

EVA_CHANNEL_ID = 2  # #eva est le 2e canal créé (après #general)
POLL_INTERVAL = 1.0  # secondes
HERMES_BIN = os.path.expanduser("~/.local/bin/hermes")
LOG_FILE = os.path.expanduser("~/chat/eva-bridge.log")

# Compte bot EVA
BOT_USERNAME = "eva"
BOT_PASSWORD = "eva-secure-key-2026"
BOT_DISPLAY_NAME = "E.V.A"

# Clé de chiffrement du bot (stockée pour déchiffrer les messages)
BOT_KEY_B64 = None

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [EVA-BRIDGE] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)


# ─── Initialisation du bot EVA ────────────────────────────────────

def ensure_bot_user():
    """Crée le compte bot EVA s'il n'existe pas."""
    global BOT_KEY_B64
    import bcrypt

    conn = get_db()
    user = conn.execute("SELECT id FROM users WHERE username = ?", (BOT_USERNAME,)).fetchone()

    if not user:
        pw_hash = bcrypt.hashpw(BOT_PASSWORD.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        cur = conn.execute(
            "INSERT INTO users (username, password_hash, display_name) VALUES (?, ?, ?)",
            (BOT_USERNAME, pw_hash, BOT_DISPLAY_NAME)
        )
        bot_id = cur.lastrowid
        log.info(f"[✓] Compte bot EVA créé (id={bot_id})")

        # Ajouter à tous les canaux
        for ch in conn.execute("SELECT id FROM channels").fetchall():
            conn.execute(
                "INSERT OR IGNORE INTO channel_members (channel_id, user_id, role) VALUES (?, ?, ?)",
                (ch['id'], bot_id, 'admin')
            )
        conn.commit()
    else:
        bot_id = user['id']
        log.info(f"[i] Compte bot EVA existant (id={bot_id})")

    # Dériver la clé de chiffrement
    key, _ = derive_key(BOT_PASSWORD)
    BOT_KEY_B64 = base64.b64encode(key).decode('utf-8')

    conn.close()
    return bot_id


# ─── Pont EVA ─────────────────────────────────────────────────────

def chat_with_eva(message: str) -> str:
    """Envoie un message à EVA via hermes CLI et retourne sa réponse."""
    try:
        result = subprocess.run(
            [HERMES_BIN, "chat", "-q", message],
            capture_output=True,
            text=True,
            timeout=120,
            env={**os.environ, "HOME": os.path.expanduser("~")},
        )
        response = result.stdout.strip()
        if not response:
            response = result.stderr.strip()
        if not response:
            response = "🤖 EVA n'a pas répondu."
        return response
    except subprocess.TimeoutExpired:
        return "⏱️ EVA a mis trop de temps à répondre (timeout 120s)."
    except FileNotFoundError:
        return f"⚠️ hermes introuvable: {HERMES_BIN}"
    except Exception as e:
        return f"⚠️ Erreur pont EVA: {str(e)}"


def send_to_channel(channel_id: int, user_id: int, content: str):
    """Envoie un message dans un canal (chiffré)."""
    # Chiffrer avec la clé du bot
    key = base64.b64decode(BOT_KEY_B64)
    encrypted = encrypt_message(content, key)

    conn = get_db()
    conn.execute(
        "INSERT INTO messages (channel_id, user_id, content, content_type) VALUES (?, ?, ?, ?)",
        (channel_id, user_id, encrypted, "text")
    )
    conn.commit()
    conn.close()


def get_new_messages(channel_id: int, last_id: int) -> list:
    """Récupère les nouveaux messages depuis last_id."""
    conn = get_db()
    rows = conn.execute("""
        SELECT m.id, m.content, m.user_id, m.created_at,
               u.username, u.display_name
        FROM messages m
        JOIN users u ON u.id = m.user_id
        WHERE m.channel_id = ? AND m.id > ? AND m.is_deleted = 0
          AND u.username != ?
        ORDER BY m.id ASC
    """, (channel_id, last_id, BOT_USERNAME)).fetchall()
    conn.close()

    messages = []
    for row in rows:
        msg = dict(row)
        # Déchiffrer si possible avec le mot de passe
        decrypted = decrypt_message(msg['content'], BOT_PASSWORD)
        if decrypted is None:
            # Essayer avec la clé dérivée
            try:
                from models import decrypt_message_with_key
                key = base64.b64decode(BOT_KEY_B64)
                decrypted = decrypt_message_with_key(msg['content'], key)
            except Exception:
                decrypted = None
        msg['plaintext'] = decrypted or msg['content']
        messages.append(msg)

    return messages


# ─── Boucle principale ────────────────────────────────────────────

def main_loop():
    log.info("╔══════════════════════════════════════════╗")
    log.info("║      ADAM-CHAT — Pont EVA Bridge        ║")
    log.info("║  Relie #eva → hermes CLI → #eva         ║")
    log.info("╚══════════════════════════════════════════╝")

    bot_id = ensure_bot_user()
    last_processed_id = 0
    is_processing = False

    log.info(f"[✓] Bot EVA actif (id={bot_id})")
    log.info(f"[✓] Écoute canal #eva (id={EVA_CHANNEL_ID})")
    log.info(f"[✓] Intervalle: {POLL_INTERVAL}s")
    log.info("")

    while True:
        try:
            messages = get_new_messages(EVA_CHANNEL_ID, last_processed_id)

            for msg in messages:
                if msg['id'] <= last_processed_id:
                    continue

                last_processed_id = msg['id']

                # Éviter les boucles (ne pas répondre à ses propres messages)
                if msg['username'] == BOT_USERNAME:
                    continue

                # Ne pas traiter si déjà en train
                if is_processing:
                    log.info(f"[⋯] File d'attente: message {msg['id']} de {msg['display_name']}")
                    continue

                is_processing = True
                try:
                    user_msg = msg['plaintext']
                    log.info(f"[→] {msg['display_name']}: {user_msg[:100]}")

                    # Construire le prompt pour EVA
                    prompt = (
                        f"[Message de {msg['display_name']} via ADAM-CHAT]\n"
                        f"{user_msg}"
                    )
                    eva_response = chat_with_eva(prompt)
                    log.info(f"[←] EVA: {eva_response[:100]}")

                    # Envoyer la réponse dans le canal
                    send_to_channel(EVA_CHANNEL_ID, bot_id, eva_response)
                    log.info(f"[✓] Réponse envoyée au canal #eva")

                finally:
                    is_processing = False

            time.sleep(POLL_INTERVAL)

        except KeyboardInterrupt:
            log.info("\n[✓] Pont EVA arrêté.")
            break
        except Exception as e:
            log.error(f"[✗] Erreur: {e}")
            time.sleep(POLL_INTERVAL * 5)


def signal_handler(sig, frame):
    log.info("Signal reçu, arrêt...")
    sys.exit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    main_loop()