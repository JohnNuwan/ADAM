package store

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/JohnNuwan/ADAM/bus/broker"
)

// PostgresStore implements broker.Store with PostgreSQL
type PostgresStore struct {
	pool *pgxpool.Pool
}

func NewPostgresStore(dsn string) (*PostgresStore, error) {
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	pool, err := pgxpool.New(ctx, dsn)
	if err != nil {
		return nil, fmt.Errorf("pgxpool.New: %w", err)
	}

	if err := pool.Ping(ctx); err != nil {
		return nil, fmt.Errorf("pool.Ping: %w", err)
	}

	log.Println("[STORE] Connected to PostgreSQL")
	return &PostgresStore{pool: pool}, nil
}

func (s *PostgresStore) Save(msg broker.Message) error {
	ctx := context.Background()
	payloadJSON, _ := json.Marshal(msg.Payload)
	metaJSON, _ := json.Marshal(msg.Metadata)

	_, err := s.pool.Exec(ctx,
		`INSERT INTO events (topic, source, payload, metadata, priority, created_at)
		 VALUES ($1, $2, $3, $4, $5, $6)`,
		msg.Topic, msg.Source, payloadJSON, metaJSON, msg.Priority, msg.Timestamp,
	)
	return err
}

func (s *PostgresStore) Query(topic string, limit int) ([]broker.Message, error) {
	ctx := context.Background()
	if limit <= 0 || limit > 1000 {
		limit = 100
	}

	rows, err := s.pool.Query(ctx,
		`SELECT id, topic, source, payload, metadata, priority, created_at
		 FROM events WHERE topic = $1 ORDER BY created_at DESC LIMIT $2`, topic, limit)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var msgs []broker.Message
	for rows.Next() {
		var msg broker.Message
		var payloadJSON, metaJSON []byte
		err := rows.Scan(&msg.ID, &msg.Topic, &msg.Source, &payloadJSON, &metaJSON, &msg.Priority, &msg.Timestamp)
		if err != nil {
			return nil, err
		}
		json.Unmarshal(payloadJSON, &msg.Payload)
		json.Unmarshal(metaJSON, &msg.Metadata)
		msgs = append(msgs, msg)
	}
	return msgs, nil
}

func (s *PostgresStore) Close() {
	s.pool.Close()
}

