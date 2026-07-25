package broker

import (
	"log"
	"strings"
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

// [FIX 5] matchTopic returns true if a published topic matches a
// subscription pattern. A subscription topic may contain a trailing
// "*" to match a prefix (e.g. "adam:*" matches "adam:critic",
// "adam:scribe", etc.) or contain a "*" anywhere as a wildcard.
// We support both prefix-style ("adam:*") and full glob via
// strings.Contains-based fallback. Exact match always wins.
func matchTopic(pattern, topic string) bool {
	// exact match — fast path
	if pattern == topic {
		return true
	}
	// wildcard match: pattern ends with ":*" -> prefix match
	if strings.HasSuffix(pattern, ":*") {
		prefix := strings.TrimSuffix(pattern, "*")
		return strings.HasPrefix(topic, prefix)
	}
	// general glob: use "*" as a segment wildcard
	if strings.Contains(pattern, "*") {
		// Simple glob: split on "*", each segment must appear in order
		// e.g. "adam:*:alert" matches "adam:critic:alert"
		parts := strings.Split(pattern, "*")
		idx := 0
		for i, part := range parts {
			if part == "" {
				// leading or trailing * or ** — skip
				continue
			}
			pos := strings.Index(topic[idx:], part)
			if pos < 0 {
				return false
			}
			idx += pos + len(part)
			// For the last non-empty part, if the pattern does not
			// end with "*", it must match the end of the topic.
			if i == len(parts)-1 && !strings.HasSuffix(pattern, "*") {
				return idx == len(topic)
			}
		}
		return true
	}
	return false
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

	// [FIX 5] Collect all matching subscribers (exact + wildcard patterns)
	// Previously only "adam:*" was treated as a wildcard, so subscriptions
	// like "adam:critic:*" or "system:*" were never invoked.
	var matching []*Subscription
	for pattern, subs := range b.subs {
		if matchTopic(pattern, msg.Topic) {
			matching = append(matching, subs...)
		}
	}
	b.mu.Unlock()

	// Notify subscribers (async, panic-safe)
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

	for _, sub := range matching {
		notify(sub)
	}

	return nil
}

// Subscribe registers a handler for a topic pattern (supports wildcards
// like "adam:*", "adam:critic:*", or "system:*")
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
