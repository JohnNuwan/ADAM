package broker

import (
	"log"
	"sync"
	"time"

	"github.com/google/uuid"
)

// Message is the universal event format for ADAM nervous system
type Message struct {
	ID        string            `json:"id"`
	Topic     string            `json:"topic"`
	Source    string            `json:"source"`
	Payload   map[string]interface{} `json:"payload"`
	Metadata  map[string]string `json:"metadata,omitempty"`
	Priority  int               `json:"priority"`
	Timestamp time.Time         `json:"timestamp"`
}

// Subscription represents a registered listener
type Subscription struct {
	ID      string
	Topic   string
	Handler func(Message)
	Active  bool
}

// Broker handles pub/sub between agents
type Broker struct {
	mu            sync.RWMutex
	subs          map[string][]*Subscription // topic -> subscriptions
	history       map[string][]Message       // topic -> recent history (last 100)
	historyLimit  int
}

// Store interface for persistence
type Store interface {
	Save(msg Message) error
	Query(topic string, limit int) ([]Message, error)
}

func NewBroker() *Broker {
	return &Broker{
		subs:         make(map[string][]*Subscription),
		history:      make(map[string][]Message),
		historyLimit: 100,
	}
}

// Publish sends a message to all subscribers of the topic
func (b *Broker) Publish(msg Message) error {
	if msg.ID == "" {
		msg.ID = uuid.New().String()
	}
	if msg.Timestamp.IsZero() {
		msg.Timestamp = time.Now()
	}

	b.mu.Lock()
	// Store in history (ring buffer)
	b.history[msg.Topic] = append(b.history[msg.Topic], msg)
	if len(b.history[msg.Topic]) > b.historyLimit {
		b.history[msg.Topic] = b.history[msg.Topic][len(b.history[msg.Topic])-b.historyLimit:]
	}
	subs := b.subs[msg.Topic]
	// Also check wildcard subscribers (adam:*)
	wildcardSubs := b.subs["adam:*"]
	b.mu.Unlock()

	// Notify subscribers (async)
	notify := func(sub *Subscription) {
		if sub != nil && sub.Active {
			go func() {
				defer func() {
					if r := recover(); r != nil {
						log.Printf("[BROKER] Panic in subscriber %s: %v", sub.ID, r)
					}
				}()
				sub.Handler(msg)
			}()
		}
	}

	for _, sub := range subs {
		notify(sub)
	}
	for _, sub := range wildcardSubs {
		notify(sub)
	}

	return nil
}

// Subscribe registers a handler for a topic pattern (supports adam:* glob)
func (b *Broker) Subscribe(topic string, handler func(Message)) *Subscription {
	sub := &Subscription{
		ID:      uuid.New().String(),
		Topic:   topic,
		Handler: handler,
		Active:  true,
	}

	b.mu.Lock()
	b.subs[topic] = append(b.subs[topic], sub)
	b.mu.Unlock()

	log.Printf("[BROKER] New subscription: %s on '%s'", sub.ID[:8], topic)
	return sub
}

// Unsubscribe removes a subscription
func (b *Broker) Unsubscribe(sub *Subscription) {
	if sub == nil {
		return
	}
	b.mu.Lock()
	defer b.mu.Unlock()

	subs := b.subs[sub.Topic]
	for i, s := range subs {
		if s.ID == sub.ID {
			b.subs[sub.Topic] = append(subs[:i], subs[i+1:]...)
			break
		}
	}
	sub.Active = false
	log.Printf("[BROKER] Unsubscribed: %s", sub.ID[:8])
}

// GetHistory returns recent messages for a topic
func (b *Broker) GetHistory(topic string, limit int) []Message {
	b.mu.RLock()
	defer b.mu.RUnlock()

	msgs := b.history[topic]
	if limit > 0 && len(msgs) > limit {
		msgs = msgs[len(msgs)-limit:]
	}
	return msgs
}

// Stats returns broker statistics
func (b *Broker) Stats() map[string]interface{} {
	b.mu.RLock()
	defer b.mu.RUnlock()

	stats := make(map[string]interface{})
	stats["subscriptions"] = 0
	stats["topics"] = len(b.subs)
	totalEvents := 0
	for t, msgs := range b.history {
		totalEvents += len(msgs)
		stats["topic:"+t] = len(msgs)
	}
	stats["history_events"] = totalEvents
	for _, subs := range b.subs {
		stats["subscriptions"] = stats["subscriptions"].(int) + len(subs)
	}
	return stats
}

