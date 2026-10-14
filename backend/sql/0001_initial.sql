-- KaushalWatch protected PostgreSQL ledger v1
-- Apply with python scripts/migrate_postgres.py --apply (explicit operation).
CREATE TABLE IF NOT EXISTS kw_schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS kw_cases (
    case_id TEXT PRIMARY KEY,
    centre_id TEXT NOT NULL,
    payload JSONB NOT NULL,
    created_order BIGINT GENERATED ALWAYS AS IDENTITY UNIQUE,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT kw_case_json_object CHECK (jsonb_typeof(payload) = 'object'),
    CONSTRAINT kw_case_id_matches_payload CHECK (payload->>'case_id' = case_id),
    CONSTRAINT kw_case_centre_matches_payload CHECK (payload->>'centre_id' = centre_id)
);
CREATE INDEX IF NOT EXISTS kw_cases_centre_idx ON kw_cases (centre_id, created_order);
CREATE TABLE IF NOT EXISTS kw_analysis_history (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    centre_id TEXT NOT NULL,
    batch_id TEXT NOT NULL,
    edge_event_id TEXT UNIQUE,
    payload JSONB NOT NULL,
    CONSTRAINT kw_history_json_object CHECK (jsonb_typeof(payload) = 'object'),
    CONSTRAINT kw_history_centre_matches_payload CHECK (payload->>'centre_id' = centre_id),
    CONSTRAINT kw_history_batch_matches_payload CHECK (payload->>'batch_id' = batch_id)
);
CREATE INDEX IF NOT EXISTS kw_history_centre_idx ON kw_analysis_history (centre_id, id DESC);
CREATE TABLE IF NOT EXISTS kw_centre_settings (
    centre_id TEXT PRIMARY KEY,
    payload JSONB NOT NULL,
    CONSTRAINT kw_settings_json_object CHECK (jsonb_typeof(payload) = 'object')
);
CREATE TABLE IF NOT EXISTS kw_edge_events (
    event_id TEXT PRIMARY KEY,
    payload JSONB NOT NULL,
    received_order BIGINT GENERATED ALWAYS AS IDENTITY UNIQUE,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT kw_edge_json_object CHECK (jsonb_typeof(payload) = 'object'),
    CONSTRAINT kw_edge_id_matches_payload CHECK (payload->>'event_id' = event_id)
);
