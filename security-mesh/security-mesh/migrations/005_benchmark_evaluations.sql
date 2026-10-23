BEGIN;
CREATE TABLE IF NOT EXISTS benchmark_evaluations (
  id uuid PRIMARY KEY,
  dataset_id text NOT NULL,
  dataset_version text NOT NULL,
  score jsonb NOT NULL,
  case_results jsonb NOT NULL,
  created_by text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS benchmark_evaluations_dataset_created_idx ON benchmark_evaluations(dataset_id,dataset_version,created_at DESC);
COMMIT;
