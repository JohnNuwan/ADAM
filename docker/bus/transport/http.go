package transport

import (
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"time"

	"github.com/gorilla/websocket"
	"github.com/JohnNuwan/ADAM/bus/broker"
	"github.com/JohnNuwan/ADAM/bus/store"
)

var upgrader = websocket.Upgrader{
	CheckOrigin: func(r *http.Request) bool { return true },
}

type HTTPServer struct {
	broker *broker.Broker
	store  *store.PostgresStore
}

func NewHTTP(b *broker.Broker, s *store.PostgresStore) *HTTPServer {
	return &HTTPServer{broker: b, store: s}
}

func (h *HTTPServer) Start(port string) error {
	mux := http.NewServeMux()
	mux.HandleFunc("/api/publish", h.handlePublish)
	mux.HandleFunc("/api/subscribe", h.handleSubscribe)
	mux.HandleFunc("/api/query", h.handleQuery)
	mux.HandleFunc("/api/stats", h.handleStats)
	mux.HandleFunc("/api/health", h.handleHealth)
	mux.HandleFunc("/ws", h.handleWebSocket)

	addr := fmt.Sprintf(":%s", port)
	log.Printf("[HTTP] Listening on %s", addr)
	return http.ListenAndServe(addr, mux)
}

func (h *HTTPServer) handlePublish(w http.ResponseWriter, r *http.Request) {
	if r.Method != "POST" {
		http.Error(w, "POST required", 405)
		return
	}
	var msg broker.Message
	if err := json.NewDecoder(r.Body).Decode(&msg); err != nil {
		http.Error(w, err.Error(), 400)
		return
	}
	msg.Timestamp = time.Now()
	if err := h.broker.Publish(msg); err != nil {
		http.Error(w, err.Error(), 500)
		return
	}
	if h.store != nil {
		go func() {
			if err := h.store.Save(msg); err != nil {
				log.Printf("[HTTP] Store.Save: %v", err)
			}
		}()
	}
	w.WriteHeader(201)
	json.NewEncoder(w).Encode(map[string]string{"status": "ok", "id": msg.ID})
}

func (h *HTTPServer) handleSubscribe(w http.ResponseWriter, r *http.Request) {
	topic := r.URL.Query().Get("topic")
	if topic == "" {
		http.Error(w, "topic required", 400)
		return
	}
	sub := h.broker.Subscribe(topic, func(msg broker.Message) {})
	json.NewEncoder(w).Encode(map[string]string{
		"subscription_id": sub.ID,
		"topic":           topic,
	})
}

func (h *HTTPServer) handleQuery(w http.ResponseWriter, r *http.Request) {
	topic := r.URL.Query().Get("topic")
	limit := 100
	if h.store == nil {
		msgs := h.broker.GetHistory(topic, limit)
		json.NewEncoder(w).Encode(msgs)
		return
	}
	msgs, err := h.store.Query(topic, limit)
	if err != nil {
		http.Error(w, err.Error(), 500)
		return
	}
	if msgs == nil {
		msgs = []broker.Message{}
	}
	json.NewEncoder(w).Encode(msgs)
}

func (h *HTTPServer) handleStats(w http.ResponseWriter, r *http.Request) {
	json.NewEncoder(w).Encode(h.broker.Stats())
}

func (h *HTTPServer) handleHealth(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	w.Write([]byte(`{"status":"ok"}`))
}

func (h *HTTPServer) handleWebSocket(w http.ResponseWriter, r *http.Request) {
	conn, err := upgrader.Upgrade(w, r, nil)
	if err != nil {
		log.Printf("[WS] Upgrade: %v", err)
		return
	}
	defer conn.Close()

	type WsMessage struct {
		Action string `json:"action"`
		Topic  string `json:"topic"`
	}

	var subs []*broker.Subscription
	var wMsg WsMessage

	for {
		if err := conn.ReadJSON(&wMsg); err != nil {
			break
		}
		switch wMsg.Action {
		case "subscribe":
			sub := h.broker.Subscribe(wMsg.Topic, func(evt broker.Message) {
				conn.WriteJSON(evt)
			})
			subs = append(subs, sub)
		case "unsubscribe":
			for _, s := range subs {
				if s.Topic == wMsg.Topic {
					h.broker.Unsubscribe(s)
				}
			}
		}
	}
	for _, s := range subs {
		h.broker.Unsubscribe(s)
	}
}