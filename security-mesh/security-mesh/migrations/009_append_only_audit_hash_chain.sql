BEGIN;

ALTER TABLE execution_audit ADD COLUMN IF NOT EXISTS chain_position bigint;
ALTER TABLE execution_audit ADD COLUMN IF NOT EXISTS previous_hash text;
ALTER TABLE execution_audit ADD COLUMN IF NOT EXISTS record_hash text;

COMMIT;
