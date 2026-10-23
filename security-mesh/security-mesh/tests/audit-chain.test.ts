import { describe, expect, it } from 'vitest';
import { auditEntryHash, verifyAuditChain, type AuditChainEntry } from '../src/security/audit-chain.js';

function entry(chainPosition: number, previousHash: string | null, action: string, createdAt: string): AuditChainEntry {
  const value = {
    chain_position: chainPosition,
    id: `00000000-0000-4000-8000-${String(chainPosition).padStart(12, '0')}`,
    actor_id: 'test-actor', action, subject_type: 'test', subject_id: String(chainPosition),
    details: { targetRecordId: 'target-test', nested: { z: 2, a: 1 } }, request_id: null,
    created_at: createdAt, previous_hash: previousHash,
  };
  return { ...value, record_hash: auditEntryHash(value) };
}

describe('append-only audit hash chain', () => {
  it('verifies a correctly linked ordered chain', () => {
    const first = entry(1, null, 'workflow.created', '2026-10-19T12:00:00.000Z');
    const second = entry(2, first.record_hash, 'run.approved', '2026-10-19T12:01:00.000Z');
    expect(verifyAuditChain([first, second])).toEqual({ valid: true, entriesChecked: 2 });
  });

  it('detects changed data, broken links, and ordering gaps', () => {
    const first = entry(1, null, 'workflow.created', '2026-10-19T12:00:00.000Z');
    const second = entry(2, first.record_hash, 'run.approved', '2026-10-19T12:01:00.000Z');
    expect(verifyAuditChain([{ ...first, action: 'workflow.deleted' }, second])).toMatchObject({ valid: false, entriesChecked: 0, firstInvalidPosition: 1 });
    expect(verifyAuditChain([first, { ...second, previous_hash: 'f'.repeat(64) }])).toMatchObject({ valid: false, entriesChecked: 1, firstInvalidPosition: 2 });
    expect(verifyAuditChain([first, { ...second, chain_position: 3 }])).toMatchObject({ valid: false, entriesChecked: 1, firstInvalidPosition: 3 });
  });
});
