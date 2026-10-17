-- Phase 3H: append-only private camera-reference artifact indexes.
-- Revisions belong to an audited centre/camera proposal; never store pixels in DB.
CREATE TABLE IF NOT EXISTS kw_camera_reference_artifacts (
    centre_id TEXT NOT NULL,
    camera_id TEXT NOT NULL,
    revision INTEGER NOT NULL CHECK (revision > 0),
    object_key TEXT NOT NULL UNIQUE,
    pixel_sha256 TEXT NOT NULL CHECK (pixel_sha256 ~ '^[a-f0-9]{64}$'),
    encoded_sha256 TEXT NOT NULL CHECK (encoded_sha256 ~ '^[a-f0-9]{64}$'),
    byte_size INTEGER NOT NULL CHECK (byte_size BETWEEN 1 AND 4194304),
    width INTEGER NOT NULL CHECK (width BETWEEN 32 AND 1920),
    height INTEGER NOT NULL CHECK (height BETWEEN 32 AND 1080),
    stored_by TEXT NOT NULL,
    stored_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (centre_id, camera_id, revision),
    CONSTRAINT kw_reference_object_key CHECK (
        object_key ~ '^camera-references/v1/[A-Za-z0-9._:-]+/[A-Za-z0-9._:-]+/r[0-9]+/[a-f0-9]{32}[.]png$'
    )
);
CREATE OR REPLACE FUNCTION kw_camera_reference_artifacts_immutable()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'camera reference artifact index cannot be changed'; END;
$$;
DROP TRIGGER IF EXISTS kw_camera_ref_artifacts_immutable ON kw_camera_reference_artifacts;
CREATE TRIGGER kw_camera_ref_artifacts_immutable
BEFORE UPDATE OR DELETE ON kw_camera_reference_artifacts
FOR EACH ROW EXECUTE FUNCTION kw_camera_reference_artifacts_immutable();
CREATE INDEX IF NOT EXISTS kw_camera_ref_artifacts_by_centre
ON kw_camera_reference_artifacts (centre_id, stored_at DESC);

-- DB owner permissions can bypass triggers. Protect this table via a
-- separately provisioned runtime DB role and independently anchored logs.
-- S3 object deletion/versioning/retention must be enforced in bucket policy.
