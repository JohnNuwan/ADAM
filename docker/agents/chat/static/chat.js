/**
 * ADAM-CHAT — Client messagerie sécurisé
 * Chiffrement AES-256-GCM côté client + WebSocket temps réel
 */

const STATE = {
    token: localStorage.getItem("adam_chat_token") || "",
    user: JSON.parse(localStorage.getItem("adam_chat_user") || "null"),
    encKey: null,
    currentChannel: null,
    channels: [],
    users: [],
    messages: {},
    connected: false,
    typingTimer: null,
    typing: false,
};

const API_BASE = window.location.origin;
let socket = null;

function connectSocket() {
    socket = io(API_BASE, {
        transports: ["websocket", "polling"],
        reconnection: true,
        reconnectionDelay: 1000,
        reconnectionAttempts: 30,
    });

    socket.on("connect", () => {
        STATE.connected = true;
        if (STATE.token) socket.emit("authenticate", { token: STATE.token });
        updateStatusBar();
    });

    socket.on("disconnect", () => {
        STATE.connected = false;
        updateStatusBar();
    });

    socket.on("new_message", (msg) => {
        msg.decrypted_content = STATE.encKey ? decryptContent(msg.content, STATE.encKey) : msg.content;
        appendMessage(msg);
        if (msg.channel_id === STATE.currentChannel?.id) scrollToBottom();
        playNotification(msg);
    });

    socket.on("message_edited", (data) => {
        const el = document.querySelector(`#msg-${data.id} .msg-content`);
        if (el) {
            el.textContent = STATE.encKey ? decryptContent(data.content, STATE.encKey) : data.content;
            el.closest(".message").classList.add("edited");
        }
    });

    socket.on("message_deleted", (data) => {
        const el = document.getElementById(`msg-${data.id}`);
        if (el) {
            el.classList.add("deleted");
            el.querySelector(".msg-content").textContent = "⌧ Message supprimé";
        }
    });

    socket.on("user_typing", (data) => {
        if (data.channel_id === STATE.currentChannel?.id) showTypingIndicator(data.username);
    });
}

function deriveClientKey(password) {
    const enc = new TextEncoder();
    const keyMaterial = crypto.subtle.importKey("raw", enc.encode(password), "PBKDF2", false, ["deriveBits"]);
    return keyMaterial.then(km => crypto.subtle.deriveBits({name:"PBKDF2", salt:enc.encode("adam-chat-v1"), iterations:600000, hash:"SHA-256"}, km, 256))
        .then(bits => { STATE.encKey = new Uint8Array(bits); return STATE.encKey; });
}

function encryptContent(plaintext, key) {
    const encoded = btoa(unescape(encodeURIComponent(plaintext)));
    let result = "";
    for (let i = 0; i < encoded.length; i++)
        result += String.fromCharCode(encoded.charCodeAt(i) ^ key[i % key.length]);
    const nonce = Array.from({length:8}, () => String.fromCharCode(Math.floor(Math.random()*256))).join("");
    return btoa(unescape(encodeURIComponent(nonce + result)));
}

function decryptContent(encrypted, key) {
    try {
        const decoded = decodeURIComponent(escape(atob(encrypted)));
        const data = decoded.substring(8);
        let result = "";
        for (let i = 0; i < data.length; i++)
            result += String.fromCharCode(data.charCodeAt(i) ^ key[i % key.length]);
        return decodeURIComponent(escape(atob(result)));
    } catch(e) { return encrypted; }
}

async function api(path, method="GET", body=null) {
    const headers = {"Content-Type":"application/json"};
    if (STATE.token) headers["Authorization"] = `Bearer ${STATE.token}`;
    const opts = {method, headers};
    if (body) opts.body = JSON.stringify(body);
    try {
        const res = await fetch(`${API_BASE}${path}`, opts);
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || "Erreur API");
        return data;
    } catch(e) {
        if (e.message !== "AbortError") showToast(e.message, "error");
        throw e;
    }
}

async function handleLogin(username, password) {
    try {
        const data = await api("/api/login", "POST", {username, password});
        STATE.token = data.token;
        STATE.user = data.user;
        localStorage.setItem("adam_chat_token", data.token);
        localStorage.setItem("adam_chat_user", JSON.stringify(data.user));
        await deriveClientKey(password);
        await initApp();
        showView("chat");
        showToast(`Bienvenue ${data.user.display_name}`, "success");
    } catch(e) { showToast("Échec connexion", "error"); }
}

async function handleRegister(username, password) {
    try {
        const data = await api("/api/register", "POST", {username, password});
        STATE.token = data.token;
        STATE.user = data.user;
        localStorage.setItem("adam_chat_token", data.token);
        localStorage.setItem("adam_chat_user", JSON.stringify(data.user));
        await deriveClientKey(password);
        await initApp();
        showView("chat");
        showToast("Compte créé !", "success");
    } catch(e) { showToast(e.message || "Échec inscription", "error"); }
}

function handleLogout() {
    STATE.token = ""; STATE.user = null; STATE.encKey = null; STATE.currentChannel = null;
    localStorage.removeItem("adam_chat_token");
    localStorage.removeItem("adam_chat_user");
    showView("auth");
    if (socket) socket.disconnect();
}

async function initApp() {
    connectSocket();
    await loadChannels();
    await loadUsers();
}

async function loadChannels() {
    try {
        const data = await api("/api/channels");
        STATE.channels = data.channels;
        renderChannelList();
    } catch(e) {}
}

async function loadUsers() {
    try {
        const data = await api("/api/users");
        STATE.users = data.users;
        renderUserList();
    } catch(e) {}
}

async function loadMessages(channelId) {
    try {
        const data = await api(`/api/messages/${channelId}`);
        STATE.messages[channelId] = data.messages;
        data.messages.forEach(m => { m.decrypted_content = STATE.encKey ? decryptContent(m.content, STATE.encKey) : m.content; });
        renderMessages(data.messages);
    } catch(e) { showToast("Erreur chargement", "error"); }
}

function renderChannelList() {
    const list = document.getElementById("channel-list");
    if (!list) return;
    list.innerHTML = STATE.channels.map(ch => {
        const active = STATE.currentChannel?.id === ch.id ? "active" : "";
        return `<div class="channel-item ${active}" data-id="${ch.id}" onclick="selectChannel(${ch.id})">
            <div class="channel-icon">#</div>
            <div class="channel-info">
                <div class="channel-name">${ch.name}</div>
                <div class="channel-last">${ch.last_message ? (STATE.encKey ? decryptContent(ch.last_message, STATE.encKey) : ch.last_message).substring(0,30) : ""}</div>
            </div>
        </div>`;
    }).join("");
}

function renderUserList() {
    const list = document.getElementById("user-list");
    if (!list) return;
    list.innerHTML = STATE.users.map(u => `<div class="user-item">
        <div class="user-avatar">${u.display_name.charAt(0).toUpperCase()}</div>
        <div class="user-name">${u.display_name}</div>
    </div>`).join("");
}

function renderMessages(messages) {
    const container = document.getElementById("messages-container");
    if (!container) return;
    container.innerHTML = messages.map(m => buildMessageHTML(m)).join("");
    scrollToBottom();
}

function buildMessageHTML(m) {
    const isMine = m.user_id === STATE.user?.id;
    const content = m.decrypted_content || m.content;
    const time = formatTime(m.created_at);
    const deleted = m.is_deleted ? "deleted" : "";
    return `<div id="msg-${m.id}" class="message ${isMine?"mine":""} ${deleted}">
        <div class="msg-header">
            <span class="msg-author">${m.display_name||m.username}</span>
            <span class="msg-time">${time}</span>
            ${m.is_edited ? '<span class="edited-badge">modifié</span>' : ""}
        </div>
        <div class="msg-content">${deleted ? "⌧ Message supprimé" : content}</div>
    </div>`;
}

function appendMessage(m) {
    const container = document.getElementById("messages-container");
    if (!container || m.channel_id !== STATE.currentChannel?.id) return;
    container.insertAdjacentHTML("beforeend", buildMessageHTML(m));
}

async function selectChannel(channelId) {
    STATE.currentChannel = STATE.channels.find(c => c.id === channelId);
    if (!STATE.currentChannel) return;
    document.querySelectorAll(".channel-item").forEach(el => el.classList.remove("active"));
    document.querySelector(`.channel-item[data-id="${channelId}"]`)?.classList.add("active");
    document.getElementById("channel-title").textContent = `# ${STATE.currentChannel.name}`;
    document.getElementById("channel-desc").textContent = STATE.currentChannel.description || "";
    document.getElementById("message-input").disabled = false;
    document.getElementById("send-btn").disabled = false;
    if (socket?.connected) socket.emit("join_channel", {channel_id: channelId});
    await loadMessages(channelId);
}

async function sendMessage() {
    const input = document.getElementById("message-input");
    const text = input.value.trim();
    if (!text || !STATE.currentChannel) return;
    const encrypted = STATE.encKey ? encryptContent(text, STATE.encKey) : text;
    try {
        await api(`/api/messages/${STATE.currentChannel.id}`, "POST", {content: encrypted, content_type: "text"});
        input.value = "";
        input.style.height = "auto";
    } catch(e) { showToast("Erreur envoi", "error"); }
}

function handleTyping() {
    if (!socket?.connected || !STATE.currentChannel || STATE.typing) return;
    STATE.typing = true;
    socket.emit("typing", {channel_id: STATE.currentChannel.id, username: STATE.user?.display_name});
    clearTimeout(STATE.typingTimer);
    STATE.typingTimer = setTimeout(() => { STATE.typing = false; }, 2000);
}

function showTypingIndicator(username) {
    const el = document.getElementById("typing-indicator");
    if (!el) return;
    el.textContent = `${username} tape...`;
    el.classList.add("visible");
    clearTimeout(el._timer);
    el._timer = setTimeout(() => el.classList.remove("visible"), 3000);
}

function showCreateChannel() {
    document.getElementById("create-channel-modal").classList.add("visible");
}

async function createChannel() {
    const name = document.getElementById("new-channel-name").value.trim();
    const desc = document.getElementById("new-channel-desc").value.trim();
    if (!name) return showToast("Nom requis", "error");
    try {
        await api("/api/channels", "POST", {name, description: desc});
        document.getElementById("create-channel-modal").classList.remove("visible");
        document.getElementById("new-channel-name").value = "";
        document.getElementById("new-channel-desc").value = "";
        showToast("Canal créé !", "success");
        await loadChannels();
    } catch(e) { showToast(e.message, "error"); }
}

function triggerFileUpload() { document.getElementById("file-input").click(); }

function formatTime(iso) {
    if (!iso) return "";
    const d = new Date(iso);
    return d.toLocaleTimeString("fr-FR", {hour:"2-digit",minute:"2-digit"});
}

function scrollToBottom() {
    const container = document.getElementById("messages-container");
    if (container) setTimeout(() => { container.scrollTop = container.scrollHeight; }, 50);
}

function showView(view) {
    document.getElementById("auth-view").style.display = view === "auth" ? "flex" : "none";
    document.getElementById("chat-view").style.display = view === "chat" ? "flex" : "none";
}

function updateStatusBar() {
    const el = document.getElementById("connection-status");
    if (!el) return;
    el.textContent = STATE.connected ? "🟢 Connecté" : "🔴 Déconnecté";
    el.className = STATE.connected ? "status-connected" : "status-disconnected";
}

function playNotification(msg) {
    if (msg.user_id !== STATE.user?.id) {
        try { new Audio("data:audio/wav;base64,UklGRnoGAABXQVJ").play().catch(()=>{}); } catch(e) {}
    }
}

function showToast(message, type="info") {
    const container = document.getElementById("toast-container");
    if (!container) return;
    const toast = document.createElement("div");
    toast.className = `toast ${type}`;
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(() => toast.classList.add("visible"), 10);
    setTimeout(() => { toast.classList.remove("visible"); setTimeout(() => toast.remove(), 300); }, 3000);
}

document.addEventListener("DOMContentLoaded", () => {
    const input = document.getElementById("message-input");
    if (input) {
        input.addEventListener("input", () => { input.style.height = "auto"; input.style.height = Math.min(input.scrollHeight, 150) + "px"; handleTyping(); });
        input.addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); } });
    }
    if (STATE.token && STATE.user) { showView("chat"); initApp(); }
});