package transport

import (
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"sync"
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

// [FIX 1] handlePublish no longer persists to PG directly.
// main.go subscribes to "adam:*" on the broker and calls pgStore.Save()
// for every event, so persisting here too caused double writes.
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
	// Persistence is handled by the broker's adam:* subscriber in main.go.
	w.WriteHeader(201)
	json.NewEncoder(w).Encode(map[string]string{"status": "ok", "id": msg.ID})
}

// [FIX 3] handleSubscribe is now a real SSE (Server-Sent Events) stream.
// Clients connect with ?topic=adam:critic and receive events live.
// The connection stays open and events are flushed immediately.
func (h *HTTPServer) handleSubscribe(w http.ResponseWriter, r *http.Request) {
	topic := r.URL.Query().Get("topic")
	if topic == "" {
		http.Error(w, "topic required", 400)
		return
	}

	// SSE headers
	w.Header().Set("Content-Type", "text/event-stream")
	w.Header().Set("Cache-Control", "no-cache")
	w.Header().Set("Connection", "keep-alive")
	w.Header().Set("Access-Control-Allow-Origin", "*")

	// Check if streaming is supported (ResponseWriter Flusher)
	flusher, ok := w.(http.Flusher)
	if !ok {
		http.Error(w, "streaming not supported", 500)
		return
	}

	// Channel to receive events from the broker subscription
	eventCh := make(chan broker.Message, 64)

	sub := h.broker.Subscribe(topic, func(msg broker.Message) {
		select {
		case eventCh <- msg:
		default:
			// channel full, drop event to avoid blocking the broker
			log.Printf("[SSE] event channel full for topic %s, dropping event", topic)
		}
	})
	defer h.broker.Unsubscribe(sub)

	// Send initial ack
	fmt.Fprintf(w, "event: ready\ndata: {\"subscription_id\":%q,\"topic\":%q}\n\n", sub.ID, topic)
	flusher.Flush()

	// Notify on client disconnect
	notifyCh := r.Context().Done()

	for {
		select {
		case <-notifyCh:
			// client disconnected
			return
		case msg := <-eventCh:
			data, err := json.Marshal(msg)
			if err != nil {
				log.Printf("[SSE] marshal error: %v", err)
				continue
			}
			fmt.Fprintf(w, "event: message\ndata: %s\n\n", data)
			flusher.Flush()
		}
	}
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

// [FIX 4] WebSocket handler now uses a sync.Mutex to serialize
// conn.WriteJSON calls. The gorilla/websocket connection is not
// safe for concurrent writes — multiple subscribers pushing events
// to the same conn caused a race condition and panics.
func (h *HTTPServer) handleWebSocket(w http.ResponseWriter, r *http.Request) {
	conn, err := upgrader.Upgrade(w, r, nil)
	if err != nil {
		log.Printf("[WS] Upgrade: %v", err)
		return
	}
	defer conn.Close()

	// Mutex protects concurrent writes to the websocket connection
	var writeMu sync.Mutex

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
				writeMu.Lock()
				defer writeMu.Unlock()
				if err := conn.WriteJSON(evt); err != nil {
					log.Printf("[WS] write error: %v", err)
				}
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
