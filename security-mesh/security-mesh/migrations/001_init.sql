BEGIN;

CREATE TABLE IF NOT EXISTS authorized_scopes (
  id uuid PRIMARY KEY,
  program_slug text NOT NULL,
  repository_url text NOT NULL,
  source_commit text NOT NULL,
  chain_id integer NOT NULL CHECK (chain_id > 0),
  target_addresses text[] NOT NULL CHECK (cardinality(target_addresses) > 0),
  required_fork_block bigint NOT NULL CHECK (required_fork_block > 0),
  allowed_methods text[] NOT NULL CHECK (cardinality(allowed_methods) > 0),
  program_authorization_ref text NOT NULL,
  restrictions jsonb NOT NULL DEFAULT '{}'::jsonb,
  expires_at timestamptz NOT NULL,
  created_by text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  disabled_at timestamptz,
  UNIQUE (program_slug, repository_url, source_commit, chain_id, required_fork_block)
);
CREATE INDEX IF NOT EXISTS authorized_scopes_program_idx ON authorized_scopes(program_slug, expires_at) WHERE disabled_at IS NULL;

CREATE TABLE IF NOT EXISTS workflows (
  id uuid PRIMARY KEY,
  finding_id text,
  title text NOT NULL,
  scope_id uuid NOT NULL REFERENCES authorized_scopes(id),
  status text NOT NULL CHECK (status IN ('queued','scope_check','learning','analysis','approval_pending','execution','evidence_review','impact_review','independent_review','report_draft','human_approval','submitted','blocked','failed','timed_out','inconclusive','rejected','cancelled')),
  execution_status text NOT NULL CHECK (execution_status IN ('queued','running','passed','failed','timed_out','cancelled')) DEFAULT 'queued',
  finding_status text NOT NULL CHECK (finding_status IN ('unverified','supported','rejected','inconclusive')) DEFAULT 'unverified',
  review_status text NOT NULL CHECK (review_status IN ('pending','accepted','challenged','rejected')) DEFAULT 'pending',
  approval_status text NOT NULL CHECK (approval_status IN ('not_requested','pending','approved','denied')) DEFAULT 'not_requested',
  submission_status text NOT NULL CHECK (submission_status IN ('not_ready','drafted','submitted','acknowledged')) DEFAULT 'not_ready',
  source_commit text NOT NULL,
  chain_id integer NOT NULL CHECK (chain_id > 0),
  fork_block bigint NOT NULL CHECK (fork_block > 0),
  repository_url text NOT NULL,
  target_addresses text[] NOT NULL,
  requested_methods text[] NOT NULL,
  created_by text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS workflows_status_idx ON workflows(status, created_at DESC);
CREATE INDEX IF NOT EXISTS workflows_finding_idx ON workflows(finding_id) WHERE finding_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS workflow_scope (
  workflow_id uuid PRIMARY KEY REFERENCES workflows(id) ON DELETE RESTRICT,
  scope_id uuid NOT NULL REFERENCES authorized_scopes(id) ON DELETE RESTRICT,
  validated boolean NOT NULL,
  validation_reason text NOT NULL,
  validated_by text NOT NULL,
  validated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS agent_profiles (
  id uuid PRIMARY KEY,
  agent_id text NOT NULL UNIQUE,
  version text NOT NULL,
  profile jsonb NOT NULL,
  enabled boolean NOT NULL DEFAULT true,
  registered_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS agent_tasks (
  id uuid PRIMARY KEY,
  workflow_id uuid NOT NULL REFERENCES workflows(id) ON DELETE RESTRICT,
  agent_id text NOT NULL REFERENCES agent_profiles(agent_id),
  status text NOT NULL CHECK (status IN ('queued','running','passed','failed','timed_out','cancelled','inconclusive')),
  input jsonb NOT NULL DEFAULT '{}'::jsonb,
  output jsonb,
  error_summary text,
  attempt integer NOT NULL DEFAULT 0 CHECK (attempt >= 0),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS agent_tasks_workflow_idx ON agent_tasks(workflow_id, status);

CREATE TABLE IF NOT EXISTS skill_packs (
  id uuid PRIMARY KEY,
  skill_pack_id text NOT NULL,
  version text NOT NULL,
  content text NOT NULL,
  content_sha256 text NOT NULL,
  status text NOT NULL CHECK (status IN ('draft','evaluated','approved','rejected')) DEFAULT 'draft',
  created_by text NOT NULL,
  approved_by text,
  created_at timestamptz NOT NULL DEFAULT now(),
  approved_at timestamptz,
  UNIQUE(skill_pack_id, version)
);
CREATE TABLE IF NOT EXISTS agent_skill_bindings (
  agent_id text NOT NULL REFERENCES agent_profiles(agent_id),
  skill_pack_id text NOT NULL,
  version text NOT NULL,
  PRIMARY KEY(agent_id, skill_pack_id, version),
  FOREIGN KEY(skill_pack_id, version) REFERENCES skill_packs(skill_pack_id, version)
);
CREATE TABLE IF NOT EXISTS knowledge_entries (
  id uuid PRIMARY KEY,
  collection_id text NOT NULL,
  version text NOT NULL,
  title text NOT NULL,
  content text NOT NULL,
  source_uri text NOT NULL,
  source_sha256 text NOT NULL,
  trust_status text NOT NULL CHECK (trust_status IN ('candidate','verified','rejected')) DEFAULT 'candidate',
  provenance jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_by text NOT NULL,
  reviewed_by text,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(collection_id, version, title)
);

CREATE TABLE IF NOT EXISTS tool_registry (
  tool_id text PRIMARY KEY,
  version text NOT NULL,
  definition jsonb NOT NULL,
  enabled boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS execution_runs (
  id uuid PRIMARY KEY,
  workflow_id uuid NOT NULL REFERENCES workflows(id) ON DELETE RESTRICT,
  suite_id text NOT NULL REFERENCES tool_registry(tool_id),
  command_profile_id text NOT NULL,
  status text NOT NULL CHECK (status IN ('queued','running','passed','failed','timed_out','cancelled')) DEFAULT 'queued',
  repository_url text NOT NULL,
  source_commit text NOT NULL,
  chain_id integer NOT NULL,
  fork_block bigint NOT NULL,
  approved_by text NOT NULL,
  approval_rationale text NOT NULL,
  runner_id text,
  receipt jsonb,
  exit_code integer,
  created_at timestamptz NOT NULL DEFAULT now(),
  started_at timestamptz,
  completed_at timestamptz
);
CREATE INDEX IF NOT EXISTS execution_runs_workflow_idx ON execution_runs(workflow_id, created_at DESC);

CREATE TABLE IF NOT EXISTS artifact_manifests (
  id uuid PRIMARY KEY,
  workflow_id uuid NOT NULL REFERENCES workflows(id) ON DELETE RESTRICT,
  run_id uuid REFERENCES execution_runs(id) ON DELETE RESTRICT,
  name text NOT NULL,
  media_type text NOT NULL,
  storage_key text NOT NULL,
  sha256 text NOT NULL,
  byte_length bigint NOT NULL CHECK (byte_length >= 0),
  provenance jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_by text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(workflow_id, sha256)
);
CREATE INDEX IF NOT EXISTS artifact_manifest_workflow_idx ON artifact_manifests(workflow_id, created_at DESC);

CREATE TABLE IF NOT EXISTS evidence (
  id uuid PRIMARY KEY,
  workflow_id uuid NOT NULL REFERENCES workflows(id) ON DELETE RESTRICT,
  artifact_id uuid REFERENCES artifact_manifests(id) ON DELETE RESTRICT,
  evidence_kind text NOT NULL,
  claim text NOT NULL,
  source_ref jsonb NOT NULL DEFAULT '{}'::jsonb,
  verified boolean NOT NULL DEFAULT false,
  verification_method text,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_by text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS evidence_workflow_idx ON evidence(workflow_id, verified, created_at DESC);

CREATE TABLE IF NOT EXISTS readiness_gate_results (
  id uuid PRIMARY KEY,
  workflow_id uuid NOT NULL REFERENCES workflows(id) ON DELETE RESTRICT,
  gate_id text NOT NULL,
  outcome text NOT NULL CHECK (outcome IN ('passed','failed','inconclusive','not_applicable')),
  reasons jsonb NOT NULL DEFAULT '[]'::jsonb,
  evidence_ids uuid[] NOT NULL DEFAULT '{}',
  evaluated_by text NOT NULL,
  evaluated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(workflow_id, gate_id)
);
CREATE INDEX IF NOT EXISTS readiness_gates_workflow_idx ON readiness_gate_results(workflow_id, gate_id);

CREATE TABLE IF NOT EXISTS review_decisions (
  id uuid PRIMARY KEY,
  workflow_id uuid NOT NULL REFERENCES workflows(id) ON DELETE RESTRICT,
  decision text NOT NULL CHECK (decision IN ('accepted','challenged','rejected')),
  summary text NOT NULL,
  evidence_ids uuid[] NOT NULL DEFAULT '{}',
  reviewer_id text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS human_approvals (
  id uuid PRIMARY KEY,
  workflow_id uuid NOT NULL REFERENCES workflows(id) ON DELETE RESTRICT,
  approval_type text NOT NULL CHECK (approval_type IN ('run','skill-promotion','submission')),
  decision text NOT NULL CHECK (decision IN ('approved','denied')),
  rationale text NOT NULL,
  artifact_id uuid REFERENCES artifact_manifests(id) ON DELETE RESTRICT,
  approver_id text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS submission_records (
  id uuid PRIMARY KEY,
  workflow_id uuid NOT NULL REFERENCES workflows(id) ON DELETE RESTRICT,
  finding_id text NOT NULL,
  report_artifact_id uuid NOT NULL REFERENCES artifact_manifests(id) ON DELETE RESTRICT,
  status text NOT NULL CHECK (status IN ('drafted','approved','submitted','acknowledged')),
  authorization_id uuid REFERENCES human_approvals(id) ON DELETE RESTRICT,
  external_submission_ref text,
  created_by text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS execution_audit (
  id uuid PRIMARY KEY,
  actor_id text NOT NULL,
  action text NOT NULL,
  subject_type text NOT NULL,
  subject_id text NOT NULL,
  details jsonb NOT NULL DEFAULT '{}'::jsonb,
  request_id text,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS execution_audit_subject_idx ON execution_audit(subject_type, subject_id, created_at DESC);

CREATE OR REPLACE FUNCTION prevent_audit_mutation() RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION 'execution_audit is append-only';
END;
$$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS execution_audit_no_update ON execution_audit;
CREATE TRIGGER execution_audit_no_update BEFORE UPDATE OR DELETE ON execution_audit FOR EACH ROW EXECUTE FUNCTION prevent_audit_mutation();

COMMIT;
