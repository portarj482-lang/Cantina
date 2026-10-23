BEGIN;
CREATE TABLE IF NOT EXISTS web_assessments (
  id uuid PRIMARY KEY,
  web_scope_id uuid NOT NULL REFERENCES web_scopes(id) ON DELETE RESTRICT,
  target_host text NOT NULL,
  assessment_kind text NOT NULL CHECK (assessment_kind IN ('web-passive','email-dns')),
  results jsonb NOT NULL,
  created_by text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS web_assessments_scope_created_idx ON web_assessments(web_scope_id, created_at DESC);
COMMIT;
