-- Immutable, private retained-image metadata.
-- S3 objects are not a public URL; the server resolves these rows only after
-- an officer's centre permission and persisted case membership have passed.
CREATE TABLE IF NOT EXISTS kw_evidence_objects (
    evidence_id TEXT PRIMARY KEY,
    centre_id TEXT NOT NULL,
    object_key TEXT NOT NULL UNIQUE,
    sha256 TEXT NOT NULL,
    perceptual_hash TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT kw_evidence_sha_hex CHECK (sha256 ~ '^[0-9a-f]{64}$'),
    CONSTRAINT kw_evidence_phash_hex CHECK (perceptual_hash ~ '^[0-9a-f]{16}$'),
    CONSTRAINT kw_evidence_centre_key CHECK (
        object_key = 'evidence/v1/' || centre_id || '/' || evidence_id || '.jpg'
    )
);
CREATE INDEX IF NOT EXISTS kw_evidence_centre_history
    ON kw_evidence_objects (centre_id, created_at, evidence_id);
