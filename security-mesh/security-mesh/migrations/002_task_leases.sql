BEGIN;

ALTER TABLE agent_tasks
  ADD COLUMN IF NOT EXISTS idempotency_key text,
  ADD COLUMN IF NOT EXISTS request_sha256 text,
  ADD COLUMN IF NOT EXISTS contract_version text NOT NULL DEFAULT '1.0.0',
  ADD COLUMN IF NOT EXISTS max_attempts integer NOT NULL DEFAULT 2 CHECK (max_attempts BETWEEN 1 AND 20),
  ADD COLUMN IF NOT EXISTS available_at timestamptz NOT NULL DEFAULT now(),
  ADD COLUMN IF NOT EXISTS lease_owner text,
  ADD COLUMN IF NOT EXISTS lease_token uuid,
  ADD COLUMN IF NOT EXISTS lease_expires_at timestamptz,
  ADD COLUMN IF NOT EXISTS last_error text;

CREATE UNIQUE INDEX IF NOT EXISTS agent_tasks_idempotency_idx
  ON agent_tasks(workflow_id, idempotency_key) WHERE idempotency_key IS NOT NULL;
CREATE INDEX IF NOT EXISTS agent_tasks_claim_idx
  ON agent_tasks(status, available_at, created_at) WHERE status = 'queued';

CREATE TABLE IF NOT EXISTS agent_task_dependencies (
  task_id uuid NOT NULL REFERENCES agent_tasks(id) ON DELETE RESTRICT,
  depends_on_task_id uuid NOT NULL REFERENCES agent_tasks(id) ON DELETE RESTRICT,
  PRIMARY KEY(task_id, depends_on_task_id),
  CHECK (task_id <> depends_on_task_id)
);

COMMIT;
