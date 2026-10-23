BEGIN;
CREATE TABLE IF NOT EXISTS runner_identities (
  runner_id text PRIMARY KEY CHECK (runner_id ~ '^[A-Za-z0-9][A-Za-z0-9._:-]{2,127}$'),
  token_sha256 text NOT NULL CHECK (token_sha256 ~ '^[a-f0-9]{64}$'),
  public_key_pem text NOT NULL,
  allowed_suites text[] NOT NULL,
  enabled boolean NOT NULL DEFAULT true,
  created_by text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  rotated_at timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE execution_runs ADD COLUMN IF NOT EXISTS lease_token uuid;
ALTER TABLE execution_runs ADD COLUMN IF NOT EXISTS lease_expires_at timestamptz;
CREATE INDEX IF NOT EXISTS execution_runs_claim_idx ON execution_runs(status,created_at) WHERE status='queued';
COMMIT;
