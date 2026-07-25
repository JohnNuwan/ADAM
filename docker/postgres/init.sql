-- =============================================================================
-- ADAM — PostgreSQL Schema (remplace event_bus.db)
-- =============================================================================
-- Extensions
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ── Events (le système nerveux) ──
CREATE TABLE IF NOT EXISTS events (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    topic       VARCHAR(255) NOT NULL,
    source      VARCHAR(128) NOT NULL,        -- nom de l'agent
    payload     JSONB NOT NULL DEFAULT '{}',
    metadata    JSONB NOT NULL DEFAULT '{}',  -- headers, routing, etc
    priority    SMALLINT DEFAULT 5,           -- 1=critique → 10=debug
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    processed   BOOLEAN DEFAULT FALSE
);

CREATE INDEX idx_events_topic ON events(topic);
CREATE INDEX idx_events_source ON events(source);
CREATE INDEX idx_events_created ON events(created_at DESC);
CREATE INDEX idx_events_topic_created ON events(topic, created_at DESC);
CREATE INDEX idx_events_payload ON events USING gin(payload);
CREATE INDEX idx_events_fts ON events USING gin(to_tsvector('french', payload::text));

-- ── Abonnements (qui écoute quoi) ──
CREATE TABLE IF NOT EXISTS subscriptions (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_name  VARCHAR(128) NOT NULL,
    topic_pattern VARCHAR(255) NOT NULL,     -- supporte glob: adam:* ou exact
    endpoint    VARCHAR(512),                 -- http://agent:port/callback
    is_active   BOOLEAN DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_sub_agent ON subscriptions(agent_name);

-- ── Knowledge Graph ──
CREATE TABLE IF NOT EXISTS knowledge_nodes (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    label       VARCHAR(255) NOT NULL,        -- 'Agent', 'Project', 'Skill', 'Concept'
    name        VARCHAR(512) NOT NULL,
    properties  JSONB NOT NULL DEFAULT '{}',
    embedding   VECTOR(768),                  -- PGVector pour RAG
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS knowledge_edges (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id   UUID NOT NULL REFERENCES knowledge_nodes(id) ON DELETE CASCADE,
    target_id   UUID NOT NULL REFERENCES knowledge_nodes(id) ON DELETE CASCADE,
    relation    VARCHAR(128) NOT NULL,         -- 'DEPENDS_ON', 'CREATED_BY', 'OWNS'
    properties  JSONB NOT NULL DEFAULT '{}',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_edges_source ON knowledge_edges(source_id);
CREATE INDEX idx_edges_target ON knowledge_edges(target_id);
CREATE INDEX idx_nodes_embedding ON knowledge_nodes USING ivfflat (embedding vector_cosine_ops);

-- ── Audit / logs ──
CREATE TABLE IF NOT EXISTS audit_log (
    id          BIGSERIAL PRIMARY KEY,
    agent_name  VARCHAR(128) NOT NULL,
    action      VARCHAR(64) NOT NULL,
    target      VARCHAR(512),
    details     JSONB DEFAULT '{}',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_audit_agent ON audit_log(agent_name);
CREATE INDEX idx_audit_action ON audit_log(action);
CREATE INDEX idx_audit_created ON audit_log(created_at DESC);

-- ── Agents metadata ──
CREATE TABLE IF NOT EXISTS agents (
    name        VARCHAR(128) PRIMARY KEY,
    description TEXT,
    repo_url    VARCHAR(512),
    status      VARCHAR(32) DEFAULT 'inactive',  -- active, inactive, error
    last_heartbeat TIMESTAMPTZ,
    config      JSONB DEFAULT '{}',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── RAG Store ──
CREATE TABLE IF NOT EXISTS documents (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source      VARCHAR(255) NOT NULL,
    title       VARCHAR(512),
    content     TEXT NOT NULL,
    embedding   VECTOR(768),
    metadata    JSONB DEFAULT '{}',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_docs_embedding ON documents USING ivfflat (embedding vector_cosine_ops);
CREATE INDEX idx_docs_fts ON documents USING gin(to_tsvector('french', content));

-- ── Vues utiles ──
CREATE OR REPLACE VIEW event_stats AS
SELECT
    topic,
    source,
    count(*) as total,
    min(created_at) as first_seen,
    max(created_at) as last_seen,
    avg(extract(epoch FROM NOW() - created_at)) as avg_age_seconds
FROM events
GROUP BY topic, source;
