import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { AGENT_REGISTRY, validateAgentRegistry } from '../src/agents/registry.ts';
import { matchWorkflowToScope } from '../src/policy/scope.ts';
import { validateSourceAttestationEvidence } from '../src/policy/source-attestation.ts';
import { signReceipt, verifyExecutionReceipt } from '../src/evidence/gate.ts';
import { getSuite } from '../src/tools/registry.ts';
import { canTransition } from '../src/workflows/state-machine.ts';
import { scopeBindingSha256, validateTargetRecord } from '../src/oracles/target-record.ts';
import { authorizeTargetDispatch } from '../src/oracles/dispatch.ts';
import { selectVerificationProfile } from '../src/oracles/verification-profile.ts';
import { validateEvidencePreservation } from '../src/oracles/evidence-review.ts';

assert.equal(AGENT_REGISTRY.length, 49);
assert.deepEqual(validateAgentRegistry(), []);
assert.equal(AGENT_REGISTRY.filter((a) => a.stage === 'SOLANA' && !a.enabledForEvm).length, 5);
assert.equal(canTransition('analysis', 'approval_pending'), true);
assert.equal(canTransition('analysis', 'submitted'), false);

const workflow = {
  programSlug: 'coinbase-cantina', repositoryUrl: 'https://github.com/example/repo', sourceCommit: 'a'.repeat(40),
  chainId: 8453, targetAddresses: ['0x1111111111111111111111111111111111111111'], forkBlock: 123,
  requestedMethods: ['local-test', 'fork-test'], findingId: 'F-001', title: 'test',
};
const scope = {
  id: '00000000-0000-4000-8000-000000000001', programSlug: workflow.programSlug,
  repositoryUrl: 'https://github.com/example/repo.git/', sourceCommit: 'A'.repeat(40), chainId: 8453,
  targetAddresses: workflow.targetAddresses, requiredForkBlock: 123, allowedMethods: ['local-test', 'fork-test'],
  programAuthorizationRef: 'approved policy ref', expiresAt: '2030-01-01T00:00:00.000Z', restrictions: {},
};
assert.equal(matchWorkflowToScope(workflow, scope, new Date('2026-01-01T00:00:00Z')).ok, true);
assert.equal(matchWorkflowToScope({ ...workflow, sourceCommit: 'b'.repeat(40) }, scope).ok, false);
const sourceSha = 'c'.repeat(64);
const sourceRecords = [
  { evidence_kind: 'source-manifest', metadata: { treeSha256: sourceSha } },
  { evidence_kind: 'source-attestation', metadata: { repositoryUrl: workflow.repositoryUrl, commitSha: workflow.sourceCommit, repositoryIdentityVerified: true, commitObjectVerified: true, lineProvenanceVerified: true, sourceLineRefs: [{ path: 'src/Wallet.sol', startLine: 5, endLine: 9, excerptSha256: sourceSha }] } },
];
assert.equal(validateSourceAttestationEvidence(sourceRecords, workflow.repositoryUrl, workflow.sourceCommit).ok, true);
assert.equal(validateSourceAttestationEvidence(sourceRecords, workflow.repositoryUrl, 'b'.repeat(40)).ok, false);
assert.equal(validateSourceAttestationEvidence([{ ...sourceRecords[0] }, { ...sourceRecords[1], metadata: { ...sourceRecords[1].metadata, sourceLineRefs: [{ path: '../escape.sol', startLine: 1, endLine: 1, excerptSha256: sourceSha }] } }], workflow.repositoryUrl, workflow.sourceCommit).ok, false);

const bytes = Buffer.from('signed evidence log');
const digest = createHash('sha256').update(bytes).digest('hex');
const artifact = { name: 'run.log', uri: `sha256/${digest.slice(0, 2)}/${digest}`, sha256: digest, mediaType: 'text/plain', byteLength: bytes.length };
const secret = 'runner-shared-secret-for-smoke-check-012345';
const unsigned = {
  schemaVersion: 1, runId: '00000000-0000-4000-8000-000000000011', targetRecordId: '00000000-0000-4000-8000-000000000012', runnerId: 'isolated-test-runner', suiteId: 'revocation',
  repositoryUrl: workflow.repositoryUrl, sourceCommit: workflow.sourceCommit, chainId: 8453, forkBlock: 123,
  commandProfileId: 'f001-revocation-v1', toolVersions: { forge: '1.0.0' }, exitCode: 0, timedOut: false,
  assertions: [{ id: 'valid_pre_revocation_signature', outcome: 'passed' }, { id: 'same_digest_and_signature', outcome: 'passed' }, { id: 'post_revocation_erc1271_accepts_same_signature', outcome: 'passed' }],
  logArtifact: artifact, artifacts: [], startedAt: '2026-10-13T20:00:00.000Z', completedAt: '2026-10-13T20:00:01.000Z',
};
const receipt = { ...unsigned, signature: signReceipt(unsigned, secret) };
const suite = getSuite('revocation');
assert.ok(suite);
assert.ok(suite.requiredAssertions.includes('post_revocation_erc1271_accepts_same_signature'));
assert.ok(suite.requiredAssertions.includes('same_digest_and_signature'));
assert.ok(!suite.requiredAssertions.includes('revoked_owner_rejected'));
assert.equal(suite.dispatchEnabled, false);
const checks = await verifyExecutionReceipt(receipt, {
  runId: unsigned.runId, targetRecordId: unsigned.targetRecordId, suiteId: unsigned.suiteId, repositoryUrl: unsigned.repositoryUrl,
  sourceCommit: unsigned.sourceCommit, chainId: unsigned.chainId, forkBlock: unsigned.forkBlock,
  commandProfileId: unsigned.commandProfileId, requiredAssertions: ['valid_pre_revocation_signature', 'same_digest_and_signature', 'post_revocation_erc1271_accepts_same_signature'],
}, suite, 'isolated-test-runner', secret, { load: async (uri) => uri === artifact.uri ? bytes : Buffer.from('bad') });
assert.ok(checks.every((check) => check.outcome === 'passed'), JSON.stringify(checks));
const tampered = { ...receipt, sourceCommit: 'b'.repeat(40) };
const tamperedChecks = await verifyExecutionReceipt(tampered, {
  runId: unsigned.runId, targetRecordId: unsigned.targetRecordId, suiteId: unsigned.suiteId, repositoryUrl: unsigned.repositoryUrl,
  sourceCommit: unsigned.sourceCommit, chainId: unsigned.chainId, forkBlock: unsigned.forkBlock,
  commandProfileId: unsigned.commandProfileId, requiredAssertions: ['valid_pre_revocation_signature', 'same_digest_and_signature', 'post_revocation_erc1271_accepts_same_signature'],
}, suite, 'isolated-test-runner', secret, { load: async () => bytes });
assert.equal(tamperedChecks.find((check) => check.id === 'receipt_identity')?.outcome, 'failed');
assert.equal(tamperedChecks.find((check) => check.id === 'receipt_signature')?.outcome, 'failed');

const targetRecord = {
  id: '00000000-0000-4000-8000-000000000012',
  scopeId: scope.id,
  targetId: 'smoke-target',
  targetAddress: workflow.targetAddresses[0],
  repositoryUrl: workflow.repositoryUrl,
  sourceCommit: workflow.sourceCommit,
  chainId: workflow.chainId,
  forkBlock: workflow.forkBlock,
  environment: 'local-smoke-pinned-fork',
  allowedMethods: ['local-test', 'fork-test'],
  suiteIds: ['build'],
  expiresAt: '2029-01-01T00:00:00.000Z',
  scopeSha256: scopeBindingSha256(scope),
  programSlug: scope.programSlug,
};
assert.equal(validateTargetRecord(targetRecord, scope, new Date('2026-01-01T00:00:00Z')).outcome, 'allow');
assert.equal(validateTargetRecord({ ...targetRecord, disabledAt: '2026-02-01T00:00:00.000Z' }, scope).outcome, 'deny');
assert.equal(authorizeTargetDispatch(targetRecord, { ...workflow, targetRecordId: targetRecord.id }, new Date('2026-01-01T00:00:00Z')).outcome, 'allow');
assert.equal(authorizeTargetDispatch({ ...targetRecord, disabledAt: '2026-02-01T00:00:00.000Z' }, { ...workflow, targetRecordId: targetRecord.id }).outcome, 'deny');
assert.equal(selectVerificationProfile(targetRecord, 'build').outcome, 'allow');
assert.equal(selectVerificationProfile({ ...targetRecord, disabledAt: '2026-02-01T00:00:00.000Z' }, 'build').outcome, 'deny');
assert.equal(validateEvidencePreservation('supported', [{ verified: true, outcome: 'passed' }]).outcome, 'allow');
assert.equal(validateEvidencePreservation('supported', [{ verified: true, outcome: 'failed' }]).outcome, 'deny');

console.log(JSON.stringify({ status: 'ok', checks: ['agent-registry-49', 'solana-disabled-for-evm', 'scope-match-fail-closed', 'source-attestation-binding', 'state-machine', 'revocation-positive-oracle', 'signed-receipt', 'tamper-detection', 'target-record-validation', 'target-revocation-fail-closed', 'evidence-preservation'] }, null, 2));
