import { readFile, readdir } from 'node:fs/promises';
import { resolve } from 'node:path';
import { createHash } from 'node:crypto';
import type { Pool, PoolClient } from 'pg';
import { pool as defaultPool } from './pool.js';
import { auditEntryHash, type AuditChainEntry } from '../security/audit-chain.js';

export interface MigrationRecord {
  id: string;
  checksum: string;
  applied_at: Date;
}

export interface MigrationResult {
  applied: string[];
  skipped: string[];
}

export function computeMigrationChecksum(content: string): string {
  // Normalize line endings to avoid git crlf/lf differences causing false drift
  const normalized = content.replace(/\r\n/g, '\n');
  return createHash('sha256').update(normalized, 'utf8').digest('hex');
}

export async function ensureMigrationLedger(client: PoolClient): Promise<void> {
  await client.query(`
    CREATE TABLE IF NOT EXISTS _migrations (
      id VARCHAR(255) PRIMARY KEY,
      checksum VARCHAR(64) NOT NULL,
      applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
  `);
}

export async function backfillAuditChainWithClient(client: PoolClient): Promise<void> {
  await client.query('LOCK TABLE execution_audit IN ACCESS EXCLUSIVE MODE');
  await client.query('DROP TRIGGER IF EXISTS execution_audit_no_update ON execution_audit');
  const result = await client.query(
    'SELECT id,actor_id,action,subject_type,subject_id,details,request_id,created_at,chain_position,previous_hash,record_hash FROM execution_audit ORDER BY created_at,id'
  );
  const needsBackfill = result.rows.some((row) => row.chain_position === null || row.record_hash === null);
  if (needsBackfill) {
    let previousHash: string | null = null;
    for (let index = 0; index < result.rows.length; index++) {
      const row = result.rows[index]!;
      const entry = { ...row, chain_position: index + 1, previous_hash: previousHash } as Omit<AuditChainEntry, 'record_hash'>;
      const recordHash = auditEntryHash(entry);
      await client.query(
        'UPDATE execution_audit SET chain_position=$2,previous_hash=$3,record_hash=$4 WHERE id=$1',
        [row.id, index + 1, previousHash, recordHash]
      );
      previousHash = recordHash;
    }
  }
  await client.query('ALTER TABLE execution_audit ALTER COLUMN chain_position SET NOT NULL');
  await client.query('CREATE UNIQUE INDEX IF NOT EXISTS execution_audit_chain_position_idx ON execution_audit(chain_position)');
  await client.query(
    'CREATE TRIGGER execution_audit_no_update BEFORE UPDATE OR DELETE ON execution_audit FOR EACH ROW EXECUTE FUNCTION prevent_audit_mutation()'
  );
}

export const KNOWN_MIGRATIONS = [
  '001_init.sql',
  '002_task_leases.sql',
  '003_web_scopes.sql',
  '004_web_assessments.sql',
  '005_benchmark_evaluations.sql',
  '006_runner_identities_and_leases.sql',
  '007_target_records_and_oracle_binding.sql',
  '008_target_bound_human_decisions.sql',
  '009_append_only_audit_hash_chain.sql',
] as const;

export async function runMigrations(
  clientOrPool: Pool | PoolClient,
  migrationsDir: string = resolve(process.cwd(), 'migrations')
): Promise<MigrationResult> {
  const isPool = 'connect' in clientOrPool && typeof clientOrPool.connect === 'function';
  const client: PoolClient = isPool ? await (clientOrPool as Pool).connect() : (clientOrPool as PoolClient);

  const applied: string[] = [];
  const skipped: string[] = [];

  try {
    await ensureMigrationLedger(client);

    const existingResult = await client.query<MigrationRecord>(
      'SELECT id, checksum, applied_at FROM _migrations ORDER BY id'
    );
    const existingMap = new Map<string, string>();
    for (const row of existingResult.rows) {
      existingMap.set(row.id, row.checksum);
    }

    for (const filename of KNOWN_MIGRATIONS) {
      const filePath = resolve(migrationsDir, filename);
      const sql = await readFile(filePath, 'utf8');
      const currentChecksum = computeMigrationChecksum(sql);

      if (existingMap.has(filename)) {
        const recordedChecksum = existingMap.get(filename)!;
        if (recordedChecksum !== currentChecksum) {
          throw new Error(
            `Migration drift detected: migration "${filename}" was previously applied with checksum ${recordedChecksum}, but current file checksum is ${currentChecksum}. Migrations are immutable.`
          );
        }
        skipped.push(filename);
        continue;
      }

      // Apply migration transactionally
      await client.query('BEGIN');
      try {
        await client.query(sql);

        if (filename === '009_append_only_audit_hash_chain.sql') {
          await backfillAuditChainWithClient(client);
        }

        await client.query(
          'INSERT INTO _migrations (id, checksum, applied_at) VALUES ($1, $2, NOW())',
          [filename, currentChecksum]
        );
        await client.query('COMMIT');
        applied.push(filename);
      } catch (error) {
        await client.query('ROLLBACK');
        throw new Error(
          `Migration "${filename}" failed during execution: ${error instanceof Error ? error.message : String(error)}`
        );
      }
    }

    return { applied, skipped };
  } finally {
    if (isPool) {
      client.release();
    }
  }
}

async function main(): Promise<void> {
  const result = await runMigrations(defaultPool);
  console.log(`Migrations complete. Applied: ${result.applied.length}, Skipped (already applied): ${result.skipped.length}`);
  if (result.applied.length > 0) {
    console.log(`Applied migrations: ${result.applied.join(', ')}`);
  }
  await defaultPool.end();
}

if (process.argv[1] && process.argv[1].endsWith('migrate.ts')) {
  main().catch((error: unknown) => {
    console.error('Migration failed:', error instanceof Error ? error.message : 'unknown error');
    process.exitCode = 1;
  });
}
