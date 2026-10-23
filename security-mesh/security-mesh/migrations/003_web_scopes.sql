BEGIN;

CREATE TABLE IF NOT EXISTS web_scopes (
  id uuid PRIMARY KEY,
  program_slug text NOT NULL,
  approved_hosts text[] NOT NULL CHECK (cardinality(approved_hosts) > 0),
  allowed_methods text[] NOT NULL CHECK (cardinality(allowed_methods) > 0),
  test_account_required boolean NOT NULL DEFAULT true,
  max_requests_per_minute integer NOT NULL CHECK (max_requests_per_minute BETWEEN 1 AND 60),
  authorization_ref text NOT NULL,
  expires_at timestamptz NOT NULL,
  created_by text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  disabled_at timestamptz
);
CREATE INDEX IF NOT EXISTS web_scopes_program_idx ON web_scopes(program_slug, expires_at) WHERE disabled_at IS NULL;

COMMIT;
