import { createHash } from 'node:crypto';
import { describe, expect, it } from 'vitest';
import { signReceipt, verifyExecutionReceipt } from '../src/evidence/gate.js';
import { getSuite } from '../src/tools/registry.js';
import type { ExecutionReceipt } from '../src/types.js';

const bytes = Buffer.from('deterministic test log');
const sha = createHash('sha256').update(bytes).digest('hex');
const secret = 'runner-shared-secret-for-tests-0123456789';
const expected = {
  runId: '00000000-0000-4000-8000-000000000011',
  targetRecordId: '00000000-0000-4000-8000-000000000012',
  suiteId: 'revocation',
  repositoryUrl: 'https://github.com/example/repo',
  sourceCommit: 'a'.repeat(40),
  chainId: 8453,
  forkBlock: 123,
  commandProfileId: 'f001-revocation-v1',
  requiredAssertions: ['valid_pre_revocation_signature', 'same_digest_and_signature', 'post_revocation_erc1271_accepts_same_signature'],
};
const artifact = { name: 'run.log', uri: `sha256/${sha.slice(0, 2)}/${sha}`, sha256: sha, mediaType: 'text/plain', byteLength: bytes.length };

function makeReceipt(changes: Partial<Omit<ExecutionReceipt, 'signature'>> = {}): ExecutionReceipt {
  const unsigned: Omit<ExecutionReceipt, 'signature'> = {
    schemaVersion: 1,
    runId: expected.runId,
    targetRecordId: expected.targetRecordId,
    runnerId: 'isolated-test-runner',
    suiteId: 'revocation',
    repositoryUrl: expected.repositoryUrl,
    sourceCommit: expected.sourceCommit,
    chainId: expected.chainId,
    forkBlock: expected.forkBlock,
    commandProfileId: expected.commandProfileId,
    toolVersions: { forge: '1.0.0' },
    exitCode: 0,
    timedOut: false,
    assertions: [{ id: 'valid_pre_revocation_signature', outcome: 'passed' }, { id: 'same_digest_and_signature', outcome: 'passed' }, { id: 'post_revocation_erc1271_accepts_same_signature', outcome: 'passed' }],
    logArtifact: artifact,
    artifacts: [],
    startedAt: '2026-10-13T20:00:00.000Z',
    completedAt: '2026-10-13T20:00:01.000Z',
    ...changes,
  };
  return { ...unsigned, signature: signReceipt(unsigned, secret) };
}
const loader = { load: async (uri: string) => uri === artifact.uri ? bytes : Buffer.from('unexpected') };

describe('deterministic execution evidence gate', () => {
  it('accepts signed, pinned, assertion-complete receipts with byte-verified artifacts', async () => {
    const suite = getSuite('revocation');
    if (!suite) throw new Error('suite missing');
    const checks = await verifyExecutionReceipt(makeReceipt(), expected, suite, 'isolated-test-runner', secret, loader);
    expect(checks.every((check) => check.outcome === 'passed')).toBe(true);
  });

  it('rejects altered or mismatched receipts', async () => {
    const suite = getSuite('revocation');
    if (!suite) throw new Error('suite missing');
    const wrongCommit = makeReceipt({ sourceCommit: 'b'.repeat(40) });
    const checks = await verifyExecutionReceipt(wrongCommit, expected, suite, 'isolated-test-runner', secret, loader);
    expect(checks.find((check) => check.id === 'receipt_identity')?.outcome).toBe('failed');
  });

  it('rejects targetRecordId mismatch on receipt', async () => {
    const suite = getSuite('revocation');
    if (!suite) throw new Error('suite missing');
    const wrongTarget = makeReceipt({ targetRecordId: '00000000-0000-4000-8000-000000000999' });
    const checks = await verifyExecutionReceipt(wrongTarget, expected, suite, 'isolated-test-runner', secret, loader);
    expect(checks.find((check) => check.id === 'receipt_identity')?.outcome).toBe('failed');
  });

  it('rejects required assertions that did not pass even if the runner process exited zero', async () => {
    const suite = getSuite('revocation');
    if (!suite) throw new Error('suite missing');
    const receipt = makeReceipt({ assertions: [{ id: 'valid_pre_revocation_signature', outcome: 'passed' }, { id: 'same_digest_and_signature', outcome: 'passed' }, { id: 'post_revocation_erc1271_accepts_same_signature', outcome: 'failed' }] });
    const checks = await verifyExecutionReceipt(receipt, expected, suite, 'isolated-test-runner', secret, loader);
    expect(checks.find((check) => check.id === 'required_assertions')?.outcome).toBe('failed');
  });

  it('rejects artifact digest mismatch against the actual bytes', async () => {
    const suite = getSuite('revocation');
    if (!suite) throw new Error('suite missing');
    const wrongLoader = { load: async () => Buffer.from('changed log bytes') };
    const checks = await verifyExecutionReceipt(makeReceipt(), expected, suite, 'isolated-test-runner', secret, wrongLoader);
    expect(checks.find((check) => check.id === 'artifact_integrity')?.outcome).toBe('failed');
  });
});
