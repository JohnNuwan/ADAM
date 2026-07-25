package main

import (
	"log"
	"os"
	"os/signal"
	"syscall"

	"github.com/JohnNuwan/ADAM/bus/broker"
	"github.com/JohnNuwan/ADAM/bus/store"
	"github.com/JohnNuwan/ADAM/bus/transport"
)

func main() {
	log.SetFlags(log.Ldate | log.Ltime | log.Lshortfile)
	log.Println("[BUS] Starting ADAM Event Bus...")

	// Configuration
	pgDSN := getEnv("POSTGRES_DSN", "postgres://adam:adam_secret_2026@localhost:5432/adam?sslmode=disable")
	httpPort := getEnv("HTTP_PORT", "8086")

	// Initialize broker
	b := broker.NewBroker()

	// PostgreSQL store
	var pgStore *store.PostgresStore
	var err error
	pgStore, err = store.NewPostgresStore(pgDSN)
	if err != nil {
		log.Printf("[BUS] PostgreSQL not available: %v (running without persistence)", err)
		pgStore = nil
	}

	// Connect broker to store for automatic persistence
	if pgStore != nil {
		b.Subscribe("adam:*", func(msg broker.Message) {
			if err := pgStore.Save(msg); err != nil {
				log.Printf("[BUS] Failed to persist: %v", err)
			}
		})
		log.Println("[BUS] Auto-persistence enabled for all adam:* events")
	}

	// HTTP + WebSocket server
	httpServer := transport.NewHTTP(b, pgStore)
	go func() {
		if err := httpServer.Start(httpPort); err != nil {
			log.Fatalf("[BUS] HTTP server: %v", err)
		}
	}()

	log.Printf("[BUS] ADAM Event Bus running on port %s", httpPort)
	log.Println("[BUS] API endpoints:")
	log.Println("  POST /api/publish    - Send event")
	log.Println("  GET  /api/subscribe  - Subscribe (SSE)")
	log.Println("  GET  /api/query      - Query history")
	log.Println("  GET  /api/stats      - Broker stats")
	log.Println("  WS   /ws             - WebSocket")
	log.Println("  GET  /api/health     - Health check")

	// Wait for shutdown
	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, syscall.SIGINT, syscall.SIGTERM)
	sig := <-sigCh
	log.Printf("[BUS] Received signal: %v, shutting down...", sig)

	if pgStore != nil {
		pgStore.Close()
	}
	log.Println("[BUS] Shutdown complete")
}

func getEnv(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}
