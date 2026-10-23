BEGIN;

CREATE TABLE IF NOT EXISTS target_records (
  id uuid PRIMARY KEY,
  scope_id uuid NOT NULL REFERENCES authorized_scopes(id) ON DELETE RESTRICT,
  target_id text NOT NULL CHECK (target_id ~ '^[a-z0-9][a-z0-9-]{2,99}$'),
  target_address text NOT NULL CHECK (target_address ~* '^0x[a-f0-9]{40}$'),
  repository_url text NOT NULL,
  source_commit text NOT NULL CHECK (source_commit ~* '^(?:[a-f0-9]{40}|[a-f0-9]{64})$'),
  chain_id integer NOT NULL CHECK (chain_id > 0),
  fork_block bigint NOT NULL CHECK (fork_block > 0),
  environment text NOT NULL,
  allowed_methods text[] NOT NULL CHECK (cardinality(allowed_methods) > 0),
  suite_ids text[] NOT NULL DEFAULT '{}',
  expires_at timestamptz NOT NULL,
  scope_sha256 text NOT NULL CHECK (scope_sha256 ~ '^[a-f0-9]{64}$'),
  harness_sha256 text CHECK (harness_sha256 ~ '^[a-f0-9]{64}$'),
  status text NOT NULL CHECK (status IN ('active','revoked')) DEFAULT 'active',
  created_by text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  revoked_at timestamptz,
  UNIQUE (scope_id, target_id)
);
CREATE INDEX IF NOT EXISTS target_records_active_idx ON target_records(id, expires_at) WHERE status='active';

ALTER TABLE workflows ADD COLUMN IF NOT EXISTS target_record_id uuid REFERENCES target_records(id) ON DELETE RESTRICT;
ALTER TABLE agent_tasks ADD COLUMN IF NOT EXISTS target_record_id uuid REFERENCES target_records(id) ON DELETE RESTRICT;
ALTER TABLE execution_runs ADD COLUMN IF NOT EXISTS target_record_id uuid REFERENCES target_records(id) ON DELETE RESTRICT;
ALTER TABLE artifact_manifests ADD COLUMN IF NOT EXISTS target_record_id uuid REFERENCES target_records(id) ON DELETE RESTRICT;
ALTER TABLE evidence ADD COLUMN IF NOT EXISTS target_record_id uuid REFERENCES target_records(id) ON DELETE RESTRICT;

UPDATE workflows w SET target_record_id=t.id
FROM target_records t
WHERE w.target_record_id IS NULL AND t.scope_id=w.scope_id
  AND lower(t.repository_url)=lower(w.repository_url)
  AND lower(t.source_commit)=lower(w.source_commit)
  AND t.chain_id=w.chain_id AND t.fork_block=w.fork_block
  AND w.target_addresses <@ ARRAY[t.target_address];

CREATE INDEX IF NOT EXISTS workflows_target_record_idx ON workflows(target_record_id);
CREATE INDEX IF NOT EXISTS agent_tasks_target_record_idx ON agent_tasks(target_record_id);
CREATE INDEX IF NOT EXISTS execution_runs_target_record_idx ON execution_runs(target_record_id);
CREATE INDEX IF NOT EXISTS artifacts_target_record_idx ON artifact_manifests(target_record_id);
CREATE INDEX IF NOT EXISTS evidence_target_record_idx ON evidence(target_record_id);

COMMIT;
