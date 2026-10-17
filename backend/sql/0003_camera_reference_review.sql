-- Phase 3G: optional staging-only camera reference proposal/review metadata.
-- This schema does NOT certify or activate reference-image content.
-- Apply explicitly with migration-scoped DB credentials, never at startup.
CREATE TABLE IF NOT EXISTS kw_camera_reference_proposals (
    centre_id TEXT NOT NULL,
    camera_id TEXT NOT NULL,
    revision INTEGER NOT NULL CHECK (revision > 0),
    state TEXT NOT NULL CHECK (
        state IN ('PENDING_REVIEW','REVIEWED_NOT_BOUND','SUSPENDED','REVOKED')
    ),
    reference_digest TEXT NOT NULL CHECK (reference_digest ~ '^[0-9a-f]{64}$'),
    capture_id TEXT NOT NULL,
    source_review_id TEXT NOT NULL,
    proposed_by TEXT NOT NULL,
    reviewed_by TEXT,
    independent_review_id TEXT,
    updated_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (centre_id, camera_id)
);
CREATE TABLE IF NOT EXISTS kw_camera_reference_events (
    centre_id TEXT NOT NULL,
    camera_id TEXT NOT NULL,
    sequence INTEGER NOT NULL CHECK (sequence > 0),
    revision INTEGER NOT NULL CHECK (revision > 0),
    action TEXT NOT NULL CHECK (action IN ('PROPOSE','REVIEW','SUSPEND','REVOKE')),
    actor TEXT NOT NULL,
    happened_at TIMESTAMPTZ NOT NULL,
    summary JSONB NOT NULL CHECK (jsonb_typeof(summary) = 'object'),
    previous_hash TEXT NOT NULL CHECK (previous_hash ~ '^[0-9a-f]{64}$'),
    event_hash TEXT NOT NULL CHECK (event_hash ~ '^[0-9a-f]{64}$'),
    PRIMARY KEY (centre_id, camera_id, sequence)
);
CREATE INDEX IF NOT EXISTS kw_camera_reference_events_time_idx
    ON kw_camera_reference_events (centre_id, happened_at DESC);
CREATE OR REPLACE FUNCTION kw_camera_ref_events_append_only()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'camera reference audit cannot be changed';
END; $$;
DROP TRIGGER IF EXISTS kw_camera_ref_events_block_update ON kw_camera_reference_events;
CREATE TRIGGER kw_camera_ref_events_block_update
BEFORE UPDATE OR DELETE ON kw_camera_reference_events
FOR EACH ROW EXECUTE FUNCTION kw_camera_ref_events_append_only();

-- This protects against ordinary application-row edits only. DB owners can
-- replace triggers and hash chains; external immutability remains a release gate.
