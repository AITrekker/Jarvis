-- Initial schema. PRD §4.
-- Run with: psql "$JARVIS_DB_URL" -f migrations/0001_init.sql
-- (alembic wiring lands in Phase 1; for Phase 0 the raw SQL is the source of truth.)

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TABLE people (
    id SERIAL PRIMARY KEY,
    display_name TEXT NOT NULL,
    email TEXT UNIQUE,
    is_self BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE speaker_embeddings (
    id SERIAL PRIMARY KEY,
    person_id INT REFERENCES people(id) ON DELETE CASCADE,
    embedding VECTOR(192) NOT NULL,
    source_recording_id INT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX speaker_embeddings_embedding_idx
    ON speaker_embeddings USING ivfflat (embedding vector_cosine_ops);

CREATE TABLE events (
    id SERIAL PRIMARY KEY,
    google_event_id TEXT UNIQUE,
    title TEXT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL,
    ended_at TIMESTAMPTZ NOT NULL,
    description TEXT,
    raw_payload JSONB
);

CREATE TABLE event_attendees (
    event_id INT REFERENCES events(id) ON DELETE CASCADE,
    person_id INT REFERENCES people(id) ON DELETE CASCADE,
    response_status TEXT,
    PRIMARY KEY (event_id, person_id)
);

CREATE TABLE recordings (
    id SERIAL PRIMARY KEY,
    session_uuid UUID UNIQUE NOT NULL,
    audio_path TEXT NOT NULL,
    source_label TEXT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL,
    ended_at TIMESTAMPTZ NOT NULL,
    event_id INT REFERENCES events(id),
    summary_abstract TEXT,
    summary_action_items JSONB,
    summary_topics TEXT[],
    summary_embedding VECTOR(768),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE turns (
    id SERIAL PRIMARY KEY,
    recording_id INT REFERENCES recordings(id) ON DELETE CASCADE,
    speaker_raw TEXT NOT NULL,
    person_id INT REFERENCES people(id),
    speaker_confidence REAL,
    needs_review BOOLEAN DEFAULT FALSE,
    t_start REAL NOT NULL,
    t_end REAL NOT NULL,
    text TEXT NOT NULL,
    text_tsv TSVECTOR GENERATED ALWAYS AS (to_tsvector('english', text)) STORED
);
CREATE INDEX turns_text_tsv_idx ON turns USING GIN (text_tsv);
CREATE INDEX turns_recording_t_start_idx ON turns (recording_id, t_start);
CREATE INDEX turns_person_idx ON turns (person_id);

CREATE TABLE chunks (
    id SERIAL PRIMARY KEY,
    recording_id INT REFERENCES recordings(id) ON DELETE CASCADE,
    t_start REAL NOT NULL,
    t_end REAL NOT NULL,
    text TEXT NOT NULL,
    speakers INT[],
    embedding VECTOR(768) NOT NULL
);
CREATE INDEX chunks_embedding_idx ON chunks USING ivfflat (embedding vector_cosine_ops);
CREATE INDEX chunks_recording_idx ON chunks (recording_id);
