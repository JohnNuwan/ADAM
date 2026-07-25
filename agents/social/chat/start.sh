#!/bin/bash
# ADAM-CHAT — Script de démarrage
# Usage: ./start.sh [server|bridge|all]

cd "$(dirname "$0")"
ACTIVATE="source .venv/bin/activate"

start_server() {
    echo "🚀 Démarrage ADAM-CHAT Server (port 8085)..."
    eval "$ACTIVATE && nohup python3 server.py > ../adam-chat-server.log 2>&1 &"
    echo $! > /tmp/adam-chat-server.pid
    echo "[✓] PID: $(cat /tmp/adam-chat-server.pid)"
    sleep 2
    if curl -s http://127.0.0.1:8085/api/health > /dev/null 2>&1; then
        echo "[✓] Serveur opérationnel sur http://192.168.1.5:8085"
    else
        echo "[✗] Échec démarrage"
    fi
}

start_bridge() {
    echo "🤖 Démarrage Pont EVA..."
    eval "$ACTIVATE && nohup python3 eva-bridge.py > ../adam-chat-bridge.log 2>&1 &"
    echo $! > /tmp/adam-chat-bridge.pid
    echo "[✓] Pont EVA PID: $(cat /tmp/adam-chat-bridge.pid)"
}

stop() {
    echo "⏹  Arrêt..."
    for pid_file in /tmp/adam-chat-server.pid /tmp/adam-chat-bridge.pid; do
        if [ -f "$pid_file" ]; then
            kill $(cat "$pid_file") 2>/dev/null
            rm -f "$pid_file"
        fi
    done
    echo "[✓] Arrêté"
}

status() {
    echo "📊 Statut ADAM-CHAT:"
    if [ -f /tmp/adam-chat-server.pid ] && kill -0 $(cat /tmp/adam-chat-server.pid) 2>/dev/null; then
        echo "  Server: 🟢 (PID: $(cat /tmp/adam-chat-server.pid))"
        curl -s http://127.0.0.1:8085/api/health 2>/dev/null
    else
        echo "  Server: 🔴"
    fi
    if [ -f /tmp/adam-chat-bridge.pid ] && kill -0 $(cat /tmp/adam-chat-bridge.pid) 2>/dev/null; then
        echo "  Bridge: 🟢 (PID: $(cat /tmp/adam-chat-bridge.pid))"
    else
        echo "  Bridge: 🔴"
    fi
}

case "${1:-all}" in
    server) start_server ;;
    bridge) start_bridge ;;
    all) start_server; start_bridge ;;
    stop) stop ;;
    status) status ;;
    restart) stop; sleep 1; start_server; start_bridge ;;
    *) echo "Usage: $0 {server|bridge|all|stop|status|restart}" ;;
esac