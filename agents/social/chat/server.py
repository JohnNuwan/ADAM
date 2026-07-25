#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ADAM-CHAT — Serveur de messagerie sécurisé
Flask + Flask-SocketIO + JWT + AES-256-GCM
Port: 8085
"""

import os
import sys
import json
import time
import base64
import hashlib
from datetime import datetime, timedelta, timezone
from functools import wraps

import bcrypt
import jwt
from flask import (
    Flask, request, jsonify, render_template, session as flask_session,
    send_from_directory
)
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_cors import CORS

# Ajouter le répertoire courant au path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from models import (
    init_db, seed_default_channels, seed_admin, get_db,
    encrypt_message, decrypt_message, decrypt_message_with_key,
    derive_key, now_iso
)

# ─── Configuration ─────────────────────────────────────────────────

HOST = "0.0.0.0"
PORT = 8085
JWT_SECRET = os.urandom(32).hex()
JWT_ALGO = "HS256"
JWT_EXPIRY_HOURS = 72
DB_PATH = os.path.expanduser("~/chat/chat.db")

app = Flask(__name__, static_folder="static", template_folder="templates")
app.config["SECRET_KEY"] = os.urandom(32).hex()
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50MB uploads

# SocketIO avec threading comme fallback
socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode="threading",
    logger=False,
    engineio_logger=False,
)
CORS(app)

# ─── Rate Limiting simple ──────────────────────────────────────────

RATE_LIMIT = {}
RATE_WINDOW = 10  # secondes
RATE_MAX = 30     # requêtes max par fenêtre


def rate_limit(key: str) -> bool:
    now = time.time()
    window_key = int(now / RATE_WINDOW)
    full_key = f"{key}:{window_key}"
    count = RATE_LIMIT.get(full_key, 0)
    if count >= RATE_MAX:
        return False
    RATE_LIMIT[full_key] = count + 1
    # Nettoyer les vieilles fenêtres
    for k in list(RATE_LIMIT.keys()):
        if int(k.split(":")[-1]) < window_key - 2:
            del RATE_LIMIT[k]
    return True


# ─── Auth Helpers ──────────────────────────────────────────────────

def create_token(user_id: int, enc_key: str) -> str:
    payload = {
        "user_id": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRY_HOURS),
        "iat": datetime.now(timezone.utc),
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)

    # Stocker la session
    conn = get_db()
    conn.execute(
        "INSERT OR REPLACE INTO sessions (token, user_id, encryption_key, expires_at) VALUES (?, ?, ?, ?)",
        (token, user_id, enc_key,
         (datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRY_HOURS)).isoformat())
    )
    conn.commit()
    conn.close()
    return token


def verify_token(token: str) -> dict | None:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
        conn = get_db()
        row = conn.execute(
            "SELECT * FROM sessions WHERE token = ? AND expires_at > datetime('now')",
            (token,)
        ).fetchone()
        conn.close()
        if row:
            return payload
        return None
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get("Authorization", "").replace("Bearer ", "")
        if not token:
            token = request.args.get("token", "")
        payload = verify_token(token)
        if not payload:
            return jsonify({"error": "Non authentifié"}), 401

        if not rate_limit(f"{payload['user_id']}:rest"):
            return jsonify({"error": "Trop de requêtes"}), 429

        return f(payload["user_id"], *args, **kwargs)
    return decorated


# ─── Routes API REST ───────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("chat.html")


@app.route("/api/health")
def health():
    return jsonify({"status": "ok", "time": now_iso(), "version": "1.0.0"})


@app.route("/api/status")
def api_status():
    """Status complet du serveur de chat."""
    conn = get_db()
    try:
        user_count = conn.execute("SELECT COUNT(*) as c FROM users").fetchone()["c"]
        channel_count = conn.execute("SELECT COUNT(*) as c FROM channels").fetchone()["c"]
        msg_count = conn.execute("SELECT COUNT(*) as c FROM messages WHERE is_deleted = 0").fetchone()["c"]
    except Exception:
        user_count = channel_count = msg_count = 0
    conn.close()
    return jsonify({
        "status": "online",
        "service": "adam-chat",
        "version": "1.0.0",
        "time": now_iso(),
        "stats": {
            "users": user_count,
            "channels": channel_count,
            "messages": msg_count,
        },
        "ws_clients": len(socketio.server.eio.sockets) if hasattr(socketio, 'server') and socketio.server else 0,
    })


@app.route("/api/register", methods=["POST"])
def register():
    data = request.json
    username = data.get("username", "").strip().lower()
    password = data.get("password", "")

    if not username or not password:
        return jsonify({"error": "Username et password requis"}), 400
    if len(username) < 3 or len(username) > 32:
        return jsonify({"error": "Username: 3-32 caractères"}), 400
    if len(password) < 6:
        return jsonify({"error": "Password: min 6 caractères"}), 400

    conn = get_db()
    existing = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
    if existing:
        conn.close()
        return jsonify({"error": "Username déjà pris"}), 409

    pw_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    key, _ = derive_key(password)
    enc_key_b64 = base64.b64encode(key).decode('utf-8')

    cur = conn.execute(
        "INSERT INTO users (username, password_hash, display_name) VALUES (?, ?, ?)",
        (username, pw_hash, username)
    )
    user_id = cur.lastrowid

    # Ajouter aux canaux publics
    for ch in conn.execute("SELECT id FROM channels WHERE is_private = 0").fetchall():
        conn.execute(
            "INSERT OR IGNORE INTO channel_members (channel_id, user_id, role) VALUES (?, ?, ?)",
            (ch['id'], user_id, 'member')
        )

    conn.commit()
    token = create_token(user_id, enc_key_b64)
    conn.close()

    return jsonify({
        "token": token,
        "user": {"id": user_id, "username": username, "display_name": username}
    }), 201


@app.route("/api/login", methods=["POST"])
def login():
    data = request.json
    username = data.get("username", "").strip().lower()
    password = data.get("password", "")

    if not username or not password:
        return jsonify({"error": "Username et password requis"}), 400

    conn = get_db()
    user = conn.execute(
        "SELECT * FROM users WHERE username = ?", (username,)
    ).fetchone()

    if not user or not bcrypt.checkpw(password.encode('utf-8'), user['password_hash'].encode('utf-8')):
        conn.close()
        return jsonify({"error": "Identifiants invalides"}), 401

    key, _ = derive_key(password)
    enc_key_b64 = base64.b64encode(key).decode('utf-8')

    # Mettre à jour last_seen
    conn.execute("UPDATE users SET last_seen = datetime('now') WHERE id = ?", (user['id'],))
    conn.commit()

    token = create_token(user['id'], enc_key_b64)
    conn.close()

    return jsonify({
        "token": token,
        "user": {
            "id": user['id'],
            "username": user['username'],
            "display_name": user['display_name']
        }
    })


@app.route("/api/channels", methods=["GET"])
@require_auth
def get_channels(user_id):
    conn = get_db()
    rows = conn.execute("""
        SELECT c.*, 
            (SELECT COUNT(*) FROM channel_members WHERE channel_id = c.id) as member_count,
            (SELECT content FROM messages WHERE channel_id = c.id AND is_deleted = 0 ORDER BY created_at DESC LIMIT 1) as last_message,
            (SELECT MAX(created_at) FROM messages WHERE channel_id = c.id) as last_activity
        FROM channels c
        JOIN channel_members cm ON cm.channel_id = c.id AND cm.user_id = ?
        ORDER BY last_activity DESC, c.name ASC
    """, (user_id,)).fetchall()
    conn.close()

    return jsonify({
        "channels": [dict(r) for r in rows]
    })


@app.route("/api/channels", methods=["POST"])
@require_auth
def create_channel(user_id):
    data = request.json
    name = data.get("name", "").strip().lower().replace(" ", "-")
    description = data.get("description", "")
    is_private = data.get("is_private", False)

    if not name:
        return jsonify({"error": "Nom requis"}), 400

    conn = get_db()
    existing = conn.execute("SELECT id FROM channels WHERE name = ?", (name,)).fetchone()
    if existing:
        conn.close()
        return jsonify({"error": "Canal déjà existant"}), 409

    cur = conn.execute(
        "INSERT INTO channels (name, description, created_by, is_private) VALUES (?, ?, ?, ?)",
        (name, description, user_id, 1 if is_private else 0)
    )
    channel_id = cur.lastrowid

    # Ajouter le créateur
    conn.execute(
        "INSERT INTO channel_members (channel_id, user_id, role) VALUES (?, ?, ?)",
        (channel_id, user_id, 'admin')
    )

    # Si public, ajouter tous les users
    if not is_private:
        for u in conn.execute("SELECT id FROM users").fetchall():
            conn.execute(
                "INSERT OR IGNORE INTO channel_members (channel_id, user_id, role) VALUES (?, ?, ?)",
                (channel_id, u['id'], 'member')
            )

    conn.commit()
    conn.close()

    # Notifier tous les clients via WebSocket
    socketio.emit("channel_created", {"channel_id": channel_id, "name": name})

    return jsonify({"channel_id": channel_id, "name": name}), 201


@app.route("/api/channels/<int:channel_id>/join", methods=["POST"])
@require_auth
def join_channel(user_id, channel_id):
    conn = get_db()
    ch = conn.execute("SELECT * FROM channels WHERE id = ?", (channel_id,)).fetchone()
    if not ch:
        conn.close()
        return jsonify({"error": "Canal introuvable"}), 404

    conn.execute(
        "INSERT OR IGNORE INTO channel_members (channel_id, user_id, role) VALUES (?, ?, ?)",
        (channel_id, user_id, 'member')
    )
    conn.commit()
    conn.close()
    return jsonify({"status": "ok"})


@app.route("/api/messages/<int:channel_id>", methods=["GET"])
@require_auth
def get_messages(user_id, channel_id):
    conn = get_db()
    before_id = request.args.get("before", None)
    limit = min(int(request.args.get("limit", 50)), 200)

    if before_id:
        rows = conn.execute("""
            SELECT m.*, u.username, u.display_name
            FROM messages m
            JOIN users u ON u.id = m.user_id
            WHERE m.channel_id = ? AND m.id < ? AND m.is_deleted = 0
            ORDER BY m.created_at DESC
            LIMIT ?
        """, (channel_id, before_id, limit)).fetchall()
    else:
        rows = conn.execute("""
            SELECT m.*, u.username, u.display_name
            FROM messages m
            JOIN users u ON u.id = m.user_id
            WHERE m.channel_id = ? AND m.is_deleted = 0
            ORDER BY m.created_at DESC
            LIMIT ?
        """, (channel_id, limit)).fetchall()

    conn.close()

    # Les messages sont chiffrés côté client — on les renvoie tels quels
    messages = [dict(r) for r in rows]
    messages.reverse()  # ordre chronologique

    return jsonify({"messages": messages})


@app.route("/api/messages/<int:channel_id>", methods=["POST"])
@require_auth
def send_message(user_id, channel_id):
    data = request.json
    content = data.get("content", "").strip()
    content_type = data.get("content_type", "text")
    file_url = data.get("file_url", "")

    if not content and not file_url:
        return jsonify({"error": "Contenu vide"}), 400

    conn = get_db()
    # Vérifier membre
    member = conn.execute(
        "SELECT role FROM channel_members WHERE channel_id = ? AND user_id = ?",
        (channel_id, user_id)
    ).fetchone()
    if not member:
        conn.close()
        return jsonify({"error": "Pas membre du canal"}), 403

    cur = conn.execute(
        "INSERT INTO messages (channel_id, user_id, content, content_type, file_url) VALUES (?, ?, ?, ?, ?)",
        (channel_id, user_id, content, content_type, file_url)
    )
    msg_id = cur.lastrowid
    conn.commit()

    msg = conn.execute("""
        SELECT m.*, u.username, u.display_name
        FROM messages m
        JOIN users u ON u.id = m.user_id
        WHERE m.id = ?
    """, (msg_id,)).fetchone()
    conn.close()

    msg_dict = dict(msg)

    # Diffuser via WebSocket
    socketio.emit("new_message", msg_dict, room=f"channel_{channel_id}")

    return jsonify(msg_dict), 201


@app.route("/api/messages/<int:msg_id>/edit", methods=["PUT"])
@require_auth
def edit_message(user_id, msg_id):
    data = request.json
    content = data.get("content", "").strip()
    if not content:
        return jsonify({"error": "Contenu vide"}), 400

    conn = get_db()
    msg = conn.execute("SELECT * FROM messages WHERE id = ?", (msg_id,)).fetchone()
    if not msg:
        conn.close()
        return jsonify({"error": "Message introuvable"}), 404
    if msg['user_id'] != user_id:
        conn.close()
        return jsonify({"error": "Pas votre message"}), 403

    conn.execute(
        "UPDATE messages SET content = ?, is_edited = 1, edited_at = datetime('now') WHERE id = ?",
        (content, msg_id)
    )
    conn.commit()
    conn.close()

    socketio.emit("message_edited", {
        "id": msg_id,
        "content": content,
        "channel_id": msg['channel_id']
    }, room=f"channel_{msg['channel_id']}")

    return jsonify({"status": "ok"})


@app.route("/api/messages/<int:msg_id>", methods=["DELETE"])
@require_auth
def delete_message(user_id, msg_id):
    conn = get_db()
    msg = conn.execute("SELECT * FROM messages WHERE id = ?", (msg_id,)).fetchone()
    if not msg:
        conn.close()
        return jsonify({"error": "Message introuvable"}), 404

    # Seul l'auteur ou admin peut supprimer
    member = conn.execute(
        "SELECT role FROM channel_members WHERE channel_id = ? AND user_id = ?",
        (msg['channel_id'], user_id)
    ).fetchone()
    if msg['user_id'] != user_id and (not member or member['role'] != 'admin'):
        conn.close()
        return jsonify({"error": "Non autorisé"}), 403

    conn.execute("UPDATE messages SET is_deleted = 1 WHERE id = ?", (msg_id,))
    conn.commit()
    conn.close()

    socketio.emit("message_deleted", {
        "id": msg_id,
        "channel_id": msg['channel_id']
    }, room=f"channel_{msg['channel_id']}")

    return jsonify({"status": "ok"})


@app.route("/api/users/me", methods=["GET"])
@require_auth
def get_me(user_id):
    conn = get_db()
    user = conn.execute(
        "SELECT id, username, display_name, avatar_url, created_at, last_seen FROM users WHERE id = ?",
        (user_id,)
    ).fetchone()
    conn.close()
    if not user:
        return jsonify({"error": "Utilisateur introuvable"}), 404
    return jsonify(dict(user))


@app.route("/api/users", methods=["GET"])
@require_auth
def get_users(user_id):
    conn = get_db()
    rows = conn.execute(
        "SELECT id, username, display_name, last_seen FROM users ORDER BY username"
    ).fetchall()
    conn.close()
    return jsonify({"users": [dict(r) for r in rows]})


@app.route("/api/upload", methods=["POST"])
@require_auth
def upload_file(user_id):
    """Upload un fichier vers le canal."""
    if 'file' not in request.files:
        return jsonify({"error": "Aucun fichier"}), 400

    file = request.files['file']
    channel_id = request.form.get('channel_id', '')

    if not file.filename:
        return jsonify({"error": "Fichier vide"}), 400

    # Sécuriser le nom
    from werkzeug.utils import secure_filename
    filename = secure_filename(file.filename)
    upload_dir = os.path.expanduser("~/chat/uploads")
    os.makedirs(upload_dir, exist_ok=True)

    # Éviter collisions
    name, ext = os.path.splitext(filename)
    timestamp = int(time.time())
    safe_name = f"{name}_{timestamp}{ext}"
    filepath = os.path.join(upload_dir, safe_name)
    file.save(filepath)

    file_url = f"/uploads/{safe_name}"

    # Envoyer un message avec le fichier
    content = f"📎 {filename}"
    file_ext = ext.lower()
    content_type = "image" if file_ext in ('.jpg','.jpeg','.png','.gif','.webp') else "file"

    conn = get_db()
    member = conn.execute(
        "SELECT role FROM channel_members WHERE channel_id = ? AND user_id = ?",
        (channel_id, user_id)
    ).fetchone()

    if member:
        cur = conn.execute(
            "INSERT INTO messages (channel_id, user_id, content, content_type, file_url) VALUES (?, ?, ?, ?, ?)",
            (channel_id, user_id, content, content_type, file_url)
        )
        msg_id = cur.lastrowid
        msg = conn.execute("""
            SELECT m.*, u.username, u.display_name
            FROM messages m JOIN users u ON u.id = m.user_id
            WHERE m.id = ?
        """, (msg_id,)).fetchone()
        conn.commit()
        socketio.emit("new_message", dict(msg), room=f"channel_{channel_id}")
    conn.close()

    return jsonify({"url": file_url, "filename": filename, "size": os.path.getsize(filepath)})


@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(os.path.expanduser("~/chat/uploads"), filename)


# ─── SocketIO Events ───────────────────────────────────────────────

@socketio.on("connect")
def handle_connect():
    pass


@socketio.on("authenticate")
def handle_auth(data):
    token = data.get("token", "")
    payload = verify_token(token)
    if payload:
        emit("auth_result", {"status": "ok", "user_id": payload["user_id"]})
    else:
        emit("auth_result", {"status": "error", "error": "Token invalide"})


@socketio.on("join_channel")
def handle_join_channel(data):
    channel_id = data.get("channel_id")
    if channel_id:
        join_room(f"channel_{channel_id}")


@socketio.on("leave_channel")
def handle_leave_channel(data):
    channel_id = data.get("channel_id")
    if channel_id:
        leave_room(f"channel_{channel_id}")


@socketio.on("typing")
def handle_typing(data):
    channel_id = data.get("channel_id")
    username = data.get("username", "Inconnu")
    emit("user_typing", {
        "channel_id": channel_id,
        "username": username
    }, room=f"channel_{channel_id}", broadcast=True, include_self=False)


# ─── Démarrage ─────────────────────────────────────────────────────

def main():
    print("╔══════════════════════════════════════════╗")
    print("║      ADAM-CHAT — Messagerie Sécurisée    ║")
    print("║  Chiffrement AES-256-GCM + WebSocket     ║")
    print("╚══════════════════════════════════════════╝")

    # Initialiser la base
    init_db()
    seed_admin()
    seed_default_channels()

    print(f"\n[✓] Serveur démarré sur http://0.0.0.0:{PORT}")
    print(f"[✓] Interface web : http://192.168.1.5:{PORT}")
    print("[✓] Utilise Eventlet pour WebSocket performant\n")
    socketio.run(app, host=HOST, port=PORT, debug=False, allow_unsafe_werkzeug=True)


if __name__ == "__main__":
    main()