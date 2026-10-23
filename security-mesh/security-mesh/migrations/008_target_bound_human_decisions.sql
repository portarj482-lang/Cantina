BEGIN;

ALTER TABLE review_decisions
  ADD COLUMN IF NOT EXISTS target_record_id uuid REFERENCES target_records(id) ON DELETE RESTRICT;
ALTER TABLE human_approvals
  ADD COLUMN IF NOT EXISTS target_record_id uuid REFERENCES target_records(id) ON DELETE RESTRICT;
ALTER TABLE submission_records
  ADD COLUMN IF NOT EXISTS target_record_id uuid REFERENCES target_records(id) ON DELETE RESTRICT;

UPDATE review_decisions r SET target_record_id=w.target_record_id
FROM workflows w WHERE r.workflow_id=w.id AND r.target_record_id IS NULL;
UPDATE human_approvals a SET target_record_id=w.target_record_id
FROM workflows w WHERE a.workflow_id=w.id AND a.target_record_id IS NULL;
UPDATE submission_records s SET target_record_id=w.target_record_id
FROM workflows w WHERE s.workflow_id=w.id AND s.target_record_id IS NULL;

CREATE INDEX IF NOT EXISTS review_decisions_target_record_idx ON review_decisions(target_record_id);
CREATE INDEX IF NOT EXISTS human_approvals_target_record_idx ON human_approvals(target_record_id);
CREATE INDEX IF NOT EXISTS submission_records_target_record_idx ON submission_records(target_record_id);

COMMIT;
