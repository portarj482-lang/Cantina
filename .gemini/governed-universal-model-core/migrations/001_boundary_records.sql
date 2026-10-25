-- GUMC Symbol Boundary / quarantine registry. Apply through the project's migration runner.
CREATE TABLE IF NOT EXISTS boundary_records (
  id text PRIMARY KEY,
  project_id text NOT NULL,
  kind text NOT NULL CHECK (kind IN ('source','claim','hypothesis','decision','evidence','handoff')),
  payload jsonb NOT NULL,
  provenance jsonb NOT NULL,
  status text NOT NULL CHECK (status IN ('captured','quarantined','verified','admitted','rejected')),
  ambiguity_reasons jsonb NOT NULL DEFAULT '[]'::jsonb,
  unknown_fields jsonb NOT NULL DEFAULT '[]'::jsonb,
  evidence_ids jsonb NOT NULL DEFAULT '[]'::jsonb,
  version integer NOT NULL DEFAULT 1 CHECK (version > 0),
  created_at timestamptz NOT NULL,
  updated_at timestamptz NOT NULL
);
CREATE INDEX IF NOT EXISTS boundary_records_project_status_idx ON boundary_records(project_id, status);
CREATE INDEX IF NOT EXISTS boundary_records_created_idx ON boundary_records(project_id, created_at DESC);

CREATE TABLE IF NOT EXISTS boundary_audit_events (
  id text PRIMARY KEY,
  record_id text NOT NULL REFERENCES boundary_records(id),
  project_id text NOT NULL,
  actor text NOT NULL,
  action text NOT NULL,
  from_status text,
  to_status text NOT NULL,
  reason text NOT NULL,
  policy_version text NOT NULL,
  evidence_ids jsonb NOT NULL DEFAULT '[]'::jsonb,
  occurred_at timestamptz NOT NULL
);
CREATE INDEX IF NOT EXISTS boundary_audit_project_time_idx ON boundary_audit_events(project_id, occurred_at);

-- Production DB role should grant SELECT/INSERT only to application roles as appropriate;
-- do not grant arbitrary UPDATE/DELETE on audit events to agent-facing credentials.
