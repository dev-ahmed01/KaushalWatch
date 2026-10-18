-- Camera Trust shadow workflow. Never mutate operational compliance cases.
CREATE TABLE IF NOT EXISTS kw_camera_registry (
  camera_id UUID PRIMARY KEY,
  centre_id TEXT NOT NULL,
  label TEXT NOT NULL,
  source_alias TEXT NOT NULL,
  created_by TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(centre_id, label)
);
CREATE INDEX IF NOT EXISTS kw_camera_centre_idx ON kw_camera_registry(centre_id);
CREATE TABLE IF NOT EXISTS kw_camera_references (
  reference_id UUID PRIMARY KEY,
  camera_id UUID NOT NULL REFERENCES kw_camera_registry(camera_id),
  sha256 CHAR(64) NOT NULL,
  captured_at TIMESTAMPTZ NOT NULL,
  note TEXT NOT NULL,
  proposed_by TEXT NOT NULL,
  approved_by TEXT,
  proposed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  approved_at TIMESTAMPTZ,
  status TEXT NOT NULL CHECK(status IN ('proposed','approved','rejected')),
  CONSTRAINT kw_camera_ref_approval CHECK (
    (status = 'proposed' AND approved_by IS NULL AND approved_at IS NULL)
    OR (status != 'proposed' AND approved_by IS NOT NULL AND approved_at IS NOT NULL
        AND approved_by != proposed_by))
);
CREATE INDEX IF NOT EXISTS kw_camera_ref_idx ON kw_camera_references(camera_id, proposed_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS kw_camera_one_approved_ref ON kw_camera_references(camera_id)
  WHERE status = 'approved';
CREATE TABLE IF NOT EXISTS kw_camera_jobs (
  job_id UUID PRIMARY KEY,
  camera_id UUID NOT NULL REFERENCES kw_camera_registry(camera_id),
  source_alias TEXT NOT NULL,
  source_sha256 CHAR(64) NOT NULL,
  idempotency_key TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('queued','running','succeeded','failed','cancelled')),
  attempts INT NOT NULL DEFAULT 0 CHECK(attempts >= 0),
  leased_until TIMESTAMPTZ,
  worker_id TEXT,
  last_error TEXT,
  sample_limit INT NOT NULL CHECK(sample_limit BETWEEN 12 AND 180),
  created_by TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(camera_id,idempotency_key)
);
CREATE INDEX IF NOT EXISTS kw_camera_jobs_claim_idx ON kw_camera_jobs(status,leased_until,created_at);
CREATE TABLE IF NOT EXISTS kw_camera_observations (
  observation_id UUID PRIMARY KEY,
  camera_id UUID NOT NULL REFERENCES kw_camera_registry(camera_id),
  job_id UUID NOT NULL UNIQUE REFERENCES kw_camera_jobs(job_id),
  source_sha256 CHAR(64) NOT NULL,
  reference_id UUID REFERENCES kw_camera_references(reference_id),
  payload JSONB NOT NULL CHECK(jsonb_typeof(payload) = 'object'),
  review_status TEXT NOT NULL DEFAULT 'unreviewed'
    CHECK(review_status IN ('unreviewed','needs_followup','not_actionable','reviewed')),
  reviewer TEXT,
  review_note TEXT,
  reviewed_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS kw_camera_obs_idx ON kw_camera_observations(camera_id,created_at DESC);
CREATE TABLE IF NOT EXISTS kw_camera_audit (
  event_id UUID PRIMARY KEY,
  camera_id UUID NOT NULL REFERENCES kw_camera_registry(camera_id),
  sequence BIGINT NOT NULL,
  actor TEXT NOT NULL,
  event TEXT NOT NULL,
  payload JSONB NOT NULL CHECK(jsonb_typeof(payload)='object'),
  previous_sha256 CHAR(64) NOT NULL,
  event_sha256 CHAR(64) NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(camera_id,sequence)
);
CREATE OR REPLACE FUNCTION kw_camera_audit_immutable() RETURNS TRIGGER AS $$
BEGIN RAISE EXCEPTION 'Camera Trust audit events are immutable'; END
$$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS kw_camera_audit_no_update ON kw_camera_audit;
CREATE TRIGGER kw_camera_audit_no_update BEFORE UPDATE OR DELETE ON kw_camera_audit
 FOR EACH ROW EXECUTE FUNCTION kw_camera_audit_immutable();
