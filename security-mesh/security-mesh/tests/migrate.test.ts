import { describe, expect, it, vi, beforeAll } from 'vitest';

// Mock DB/config before importing migrate to avoid env validation
vi.mock('../src/db/pool.js', () => ({ pool: {} }));

import { computeMigrationChecksum, runMigrations, KNOWN_MIGRATIONS } from '../src/db/migrate.js';
import type { PoolClient } from 'pg';

describe('Database Migration Ledger and Drift Detection', () => {
  it('computes deterministic SHA-256 checksums normalized across CRLF and LF', () => {
    const lf = 'CREATE TABLE test (\n  id SERIAL PRIMARY KEY\n);\n';
    const crlf = 'CREATE TABLE test (\r\n  id SERIAL PRIMARY KEY\r\n);\r\n';
    expect(computeMigrationChecksum(lf)).toBe(computeMigrationChecksum(crlf));
    expect(computeMigrationChecksum(lf)).toHaveLength(64);
  });

  it('runs all known migrations on a fresh database and records checksums', async () => {
    const executedQueries: string[] = [];
    const mockClient = {
      query: vi.fn(async (text: string) => {
        executedQueries.push(typeof text === 'string' ? text : String(text));
        if (typeof text === 'string' && text.includes('SELECT id, checksum, applied_at FROM _migrations')) {
          return { rows: [] };
        }
        if (typeof text === 'string' && text.includes('SELECT id,actor_id,action')) {
          return { rows: [] };
        }
        return { rows: [], rowCount: 0 };
      }),
      release: vi.fn(),
    } as unknown as PoolClient;

    const result = await runMigrations(mockClient);

    expect(result.applied).toEqual([...KNOWN_MIGRATIONS]);
    expect(result.skipped).toEqual([]);

    expect(executedQueries.some((q) => q.includes('CREATE TABLE IF NOT EXISTS _migrations'))).toBe(true);
    const inserts = executedQueries.filter((q) => q.includes('INSERT INTO _migrations'));
    expect(inserts.length).toBe(KNOWN_MIGRATIONS.length);
  });

  it('is idempotent on subsequent runs when checksums match', async () => {
    const { readFile } = await import('node:fs/promises');
    const { resolve } = await import('node:path');

    const rows = await Promise.all(
      KNOWN_MIGRATIONS.map(async (filename) => {
        const sql = await readFile(resolve(process.cwd(), 'migrations', filename), 'utf8');
        return { id: filename, checksum: computeMigrationChecksum(sql), applied_at: new Date() };
      })
    );

    const mockClient = {
      query: vi.fn(async (text: string) => {
        if (typeof text === 'string' && text.includes('SELECT id, checksum, applied_at FROM _migrations')) {
          return { rows };
        }
        return { rows: [], rowCount: 0 };
      }),
      release: vi.fn(),
    } as unknown as PoolClient;

    const result = await runMigrations(mockClient);
    expect(result.applied).toEqual([]);
    expect(result.skipped).toEqual([...KNOWN_MIGRATIONS]);
  });

  it('fails closed and throws an error if migration drift is detected', async () => {
    const mockClient = {
      query: vi.fn(async (text: string) => {
        if (typeof text === 'string' && text.includes('SELECT id, checksum, applied_at FROM _migrations')) {
          return {
            rows: [{ id: '001_init.sql', checksum: '0'.repeat(64), applied_at: new Date() }],
          };
        }
        return { rows: [], rowCount: 0 };
      }),
      release: vi.fn(),
    } as unknown as PoolClient;

    await expect(runMigrations(mockClient)).rejects.toThrow(/Migration drift detected: migration "001_init.sql"/);
  });

  it('rolls back the active transaction if a migration query fails', async () => {
    const executedQueries: string[] = [];
    let migrationBodyCalls = 0;

    const mockClient = {
      query: vi.fn(async (text: string) => {
        const q = typeof text === 'string' ? text : String(text);
        executedQueries.push(q);
        if (q.includes('SELECT id, checksum, applied_at FROM _migrations')) return { rows: [] };
        // Let control queries pass; fail on the second raw migration SQL body
        const isControlQuery = q.includes('CREATE TABLE IF NOT EXISTS _migrations') ||
          q === 'BEGIN' || q === 'COMMIT' || q === 'ROLLBACK' ||
          q.includes('INSERT INTO _migrations');
        if (!isControlQuery) {
          migrationBodyCalls++;
          if (migrationBodyCalls === 2) throw new Error('Simulated syntax error in migration');
        }
        return { rows: [], rowCount: 0 };
      }),
      release: vi.fn(),
    } as unknown as PoolClient;

    await expect(runMigrations(mockClient)).rejects.toThrow(/failed during execution/);
    expect(executedQueries).toContain('ROLLBACK');
  });
});
