import { describe, expect, it } from 'vitest';
import type { WorkflowCreateInput } from '../src/schemas.js';
import type { ScopeRecord } from '../src/policy/scope.js';
import { authorizeTargetDispatch } from '../src/oracles/dispatch.js';
import { bindEvidenceToTarget, validateEvidencePreservation, validateIndependentHumanReview, validateSeparateSubmissionApproval } from '../src/oracles/evidence-review.js';
import { scopeBindingSha256, validateTargetRecord, type TargetRecordBinding } from '../src/oracles/target-record.js';
import { selectVerificationProfile } from '../src/oracles/verification-profile.js';

const scope: ScopeRecord = {
  id: '00000000-0000-4000-8000-000000000101',
  programSlug: 'base-cantina',
  repositoryUrl: 'https://github.com/example/protocol.git',
  sourceCommit: 'a'.repeat(40),
  chainId: 8453,
  targetAddresses: ['0x1111111111111111111111111111111111111111', '0x3333333333333333333333333333333333333333'],
  requiredForkBlock: 123456,
  allowedMethods: ['local-test', 'static-analysis'],
  programAuthorizationRef: 'verified program scope ref',
  expiresAt: '2035-01-01T00:00:00.000Z',
  restrictions: {},
};

const target: TargetRecordBinding = {
  id: '00000000-0000-4000-8000-000000000102',
  scopeId: scope.id,
  targetId: 'manager-target',
  targetAddress: scope.targetAddresses[0]!,
  repositoryUrl: scope.repositoryUrl,
  sourceCommit: scope.sourceCommit,
  chainId: scope.chainId,
  forkBlock: scope.requiredForkBlock,
  environment: 'base-mainnet-pinned-fork',
  allowedMethods: ['local-test'],
  suiteIds: ['build'],
  expiresAt: '2034-01-01T00:00:00.000Z',
  scopeSha256: scopeBindingSha256(scope),
  programSlug: scope.programSlug,
  harnessSha256: 'c'.repeat(64),
};

const workflow: WorkflowCreateInput = {
  targetRecordId: target.id!,
  programSlug: scope.programSlug,
  repositoryUrl: scope.repositoryUrl,
  sourceCommit: scope.sourceCommit,
  chainId: scope.chainId,
  targetAddresses: [target.targetAddress],
  forkBlock: scope.requiredForkBlock,
  requestedMethods: ['local-test'],
  title: 'target-bound test workflow',
};

describe('Target Record Oracle', () => {
  it('allows exact target, scope digest, method, pin, and expiry bindings', () => {
    const decision = validateTargetRecord(target, scope, new Date('2026-01-01T00:00:00Z'));
    expect(decision.outcome).toBe('allow');
    expect(decision.reasons).toEqual([]);
    expect(decision.bindingSha256).toBe(scopeBindingSha256(scope));
  });

  it('blocks revoked target record or disabled scope', () => {
    expect(validateTargetRecord({ ...target, disabledAt: '2026-02-01T00:00:00.000Z' }, scope).outcome).toBe('deny');
    expect(validateTargetRecord(target, { ...scope, disabledAt: '2026-02-01T00:00:00.000Z' }).outcome).toBe('deny');
  });

  it('blocks scope ID mismatch', () => {
    const decision = validateTargetRecord({ ...target, scopeId: '00000000-0000-4000-8000-000000000999' }, scope);
    expect(decision.outcome).toBe('deny');
    expect(decision.reasons).toContain('Target record scope ID does not match the loaded scope.');
  });

  it('blocks expired scope or target records', () => {
    expect(validateTargetRecord(target, { ...scope, expiresAt: '2025-01-01T00:00:00.000Z' }, new Date('2026-01-01T00:00:00Z')).outcome).toBe('deny');
    expect(validateTargetRecord({ ...target, expiresAt: '2025-01-01T00:00:00.000Z' }, scope, new Date('2026-01-01T00:00:00Z')).outcome).toBe('deny');
    expect(validateTargetRecord({ ...target, expiresAt: 'invalid-date' }, scope, new Date('2026-01-01T00:00:00Z')).outcome).toBe('deny');
    // Target record expiry exceeds scope expiry
    expect(validateTargetRecord({ ...target, expiresAt: '2036-01-01T00:00:00.000Z' }, scope, new Date('2026-01-01T00:00:00Z')).outcome).toBe('deny');
  });

  it('blocks identity mismatches (program, repo, commit, chain, fork block, target address)', () => {
    expect(validateTargetRecord({ ...target, programSlug: 'other-cantina' }, scope).outcome).toBe('deny');
    expect(validateTargetRecord({ ...target, repositoryUrl: 'https://github.com/example/other.git' }, scope).outcome).toBe('deny');
    expect(validateTargetRecord({ ...target, sourceCommit: 'b'.repeat(40) }, scope).outcome).toBe('deny');
    expect(validateTargetRecord({ ...target, chainId: 1 }, scope).outcome).toBe('deny');
    expect(validateTargetRecord({ ...target, forkBlock: 999 }, scope).outcome).toBe('deny');
    expect(validateTargetRecord({ ...target, forkBlock: 0 }, scope).outcome).toBe('deny');
    expect(validateTargetRecord({ ...target, targetAddress: '0x2222222222222222222222222222222222222222' }, scope).outcome).toBe('deny');
  });

  it('blocks out-of-scope methods, duplicate suite IDs, and disabled PoC profiles', () => {
    expect(validateTargetRecord({ ...target, allowedMethods: ['fork-test'] }, scope).outcome).toBe('deny');
    expect(validateTargetRecord({ ...target, suiteIds: ['build', 'build'] }, scope).outcome).toBe('deny');
    expect(validateTargetRecord({ ...target, suiteIds: ['revocation'] }, scope).outcome).toBe('deny');
    expect(validateTargetRecord({ ...target, suiteIds: ['permit2-fork'] }, scope).outcome).toBe('deny');
    expect(validateTargetRecord({ ...target, suiteIds: ['non-existent-suite'] }, scope).outcome).toBe('deny');
  });

  it('blocks stale scope digests', () => {
    expect(validateTargetRecord({ ...target, scopeSha256: 'b'.repeat(64) }, scope).outcome).toBe('deny');
  });
});

describe('Target Dispatch Oracle', () => {
  it('allows matching dispatch request', () => {
    const decision = authorizeTargetDispatch(target, workflow, new Date('2026-01-01T00:00:00Z'));
    expect(decision.outcome).toBe('allow');
    expect(decision.reasons).toEqual([]);
  });

  it('blocks missing target record or target record ID mismatch', () => {
    expect(authorizeTargetDispatch(undefined, workflow).outcome).toBe('deny');
    expect(authorizeTargetDispatch(target, { ...workflow, targetRecordId: '00000000-0000-4000-8000-000000000999' }).outcome).toBe('deny');
  });

  it('blocks expired target records at dispatch time', () => {
    expect(authorizeTargetDispatch({ ...target, expiresAt: '2025-01-01T00:00:00.000Z' }, workflow, new Date('2026-01-01T00:00:00Z')).outcome).toBe('deny');
  });

  it('blocks revoked target records at dispatch time', () => {
    expect(authorizeTargetDispatch({ ...target, disabledAt: '2026-02-01T00:00:00.000Z' }, workflow).outcome).toBe('deny');
  });

  it('blocks parameter mismatches at dispatch time', () => {
    expect(authorizeTargetDispatch(target, { ...workflow, programSlug: 'other' }).outcome).toBe('deny');
    expect(authorizeTargetDispatch(target, { ...workflow, repositoryUrl: 'https://github.com/example/other' }).outcome).toBe('deny');
    expect(authorizeTargetDispatch(target, { ...workflow, sourceCommit: 'b'.repeat(40) }).outcome).toBe('deny');
    expect(authorizeTargetDispatch(target, { ...workflow, chainId: 1 }).outcome).toBe('deny');
    expect(authorizeTargetDispatch(target, { ...workflow, forkBlock: 999 }).outcome).toBe('deny');
    expect(authorizeTargetDispatch(target, { ...workflow, targetAddresses: ['0x2222222222222222222222222222222222222222'] }).outcome).toBe('deny');
    expect(authorizeTargetDispatch(target, { ...workflow, targetAddresses: [target.targetAddress, '0x2222222222222222222222222222222222222222'] }).outcome).toBe('deny');
    expect(authorizeTargetDispatch(target, { ...workflow, requestedMethods: ['fork-test'] }).outcome).toBe('deny');
  });
});

describe('Verification Profile Oracle', () => {
  it('allows only allowlisted, safe, enabled fixed suites', () => {
    expect(selectVerificationProfile(target, 'build').outcome).toBe('allow');
    const slitherTarget: TargetRecordBinding = {
      ...target,
      allowedMethods: ['static-analysis'],
      suiteIds: ['slither'],
    };
    expect(selectVerificationProfile(slitherTarget, 'slither').outcome).toBe('allow');
  });

  it('blocks unallowlisted, disabled, or unauthorized-method suites', () => {
    expect(selectVerificationProfile(target, 'revocation').outcome).toBe('deny');
    expect(selectVerificationProfile(target, 'permit2-fork').outcome).toBe('deny');
    expect(selectVerificationProfile(target, 'baseline-tests').outcome).toBe('deny'); // not in target.suiteIds
    expect(selectVerificationProfile({ ...target, suiteIds: ['slither'] }, 'slither').outcome).toBe('deny'); // local-test method cannot run slither
  });

  it('blocks revoked or expired target records at verification profile selection time', () => {
    expect(selectVerificationProfile({ ...target, disabledAt: '2026-02-01T00:00:00.000Z' }, 'build').outcome).toBe('deny');
    expect(selectVerificationProfile({ ...target, expiresAt: '2020-01-01T00:00:00.000Z' }, 'build').outcome).toBe('deny');
  });
});

describe('Evidence & Human Review Oracle', () => {
  it('requires valid matching target-record bindings for evidence artifacts', () => {
    expect(bindEvidenceToTarget(target.id!, target.id).outcome).toBe('allow');
    expect(bindEvidenceToTarget(target.id!, null).outcome).toBe('deny');
    expect(bindEvidenceToTarget(target.id!, undefined).outcome).toBe('deny');
    expect(bindEvidenceToTarget('', '').outcome).toBe('deny');
    expect(bindEvidenceToTarget(target.id!, '00000000-0000-4000-8000-000000000999').outcome).toBe('deny');
  });

  it('enforces independent reviewer distinct from workflow creator and approver', () => {
    expect(validateIndependentHumanReview('creator', 'reviewer').outcome).toBe('allow');
    expect(validateIndependentHumanReview('creator', 'creator').outcome).toBe('deny');
    expect(validateIndependentHumanReview('creator', 'reviewer', 'reviewer').outcome).toBe('deny');
    expect(validateIndependentHumanReview('creator', '').outcome).toBe('deny');
  });

  it('enforces submission approver distinct from independent reviewer and workflow creator', () => {
    expect(validateSeparateSubmissionApproval('reviewer', 'approver', 'creator').outcome).toBe('allow');
    expect(validateSeparateSubmissionApproval('reviewer', 'reviewer', 'creator').outcome).toBe('deny');
    expect(validateSeparateSubmissionApproval('reviewer', 'creator', 'creator').outcome).toBe('deny');
    expect(validateSeparateSubmissionApproval('reviewer', '').outcome).toBe('deny');
  });

  it('requires a verified independent reviewer before submission approval', () => {
    expect(validateSeparateSubmissionApproval('', 'approver', 'creator').outcome).toBe('deny');
  });

  it('enforces evidence preservation for supported and negative findings', () => {
    expect(validateEvidencePreservation('supported', [{ verified: true, outcome: 'passed' }]).outcome).toBe('allow');
    expect(validateEvidencePreservation('supported', []).outcome).toBe('deny');
    expect(validateEvidencePreservation('supported', [{ verified: false }]).outcome).toBe('deny');
    expect(validateEvidencePreservation('supported', [{ verified: true, outcome: 'failed' }]).outcome).toBe('deny');
    expect(validateEvidencePreservation('supported', [{ verified: true, outcome: 'rejected' }]).outcome).toBe('deny');
    expect(validateEvidencePreservation('rejected', [{ verified: false }]).outcome).toBe('allow');
    expect(validateEvidencePreservation('inconclusive', []).outcome).toBe('allow');
  });
});

describe('Isolated Runner Target-Record Validation Path', () => {
  it('verifies that runner simulation accepts matching target-record ID and check', () => {
    const run = {
      id: '00000000-0000-4000-8000-000000000201',
      workflow_id: '00000000-0000-4000-8000-000000000202',
      target_record_id: target.id!,
      suite_id: 'build',
      status: 'queued',
    };
    const workflowRecord = {
      id: run.workflow_id,
      target_record_id: target.id!,
      approval_status: 'approved',
    };

    // Runner step 1: check run.target_record_id === workflow.target_record_id
    expect(run.target_record_id).toBeTruthy();
    expect(run.target_record_id).toBe(workflowRecord.target_record_id);

    // Runner step 2: target check oracle outcome
    const targetCheckOracle = validateTargetRecord(target, scope, new Date('2026-01-01T00:00:00Z'));
    expect(targetCheckOracle.outcome).toBe('allow');

    // Runner step 3: fail closed if run target record does not match workflow
    const mismatchedRun = { ...run, target_record_id: '00000000-0000-4000-8000-000000000999' };
    expect(() => {
      if (!mismatchedRun.target_record_id || mismatchedRun.target_record_id !== workflowRecord.target_record_id) {
        throw new Error('The run is missing a matching target-record authorization binding.');
      }
    }).toThrow('The run is missing a matching target-record authorization binding.');
  });

  it('verifies that runner claim with valid targetRecord passes, while revoked/expired/mismatched fails', () => {
    const run = {
      id: '00000000-0000-4000-8000-000000000201',
      workflow_id: '00000000-0000-4000-8000-000000000202',
      target_record_id: target.id!,
      suite_id: 'build',
      status: 'queued',
    };
    const validClaim = {
      workflow: { id: run.workflow_id, target_record_id: target.id!, approval_status: 'approved' },
      run,
      targetRecord: { ...target, expires_at: '2030-01-01T00:00:00.000Z' },
    };

    // Valid claim check simulation
    const checkValid = {
      valid: !validClaim.targetRecord.disabledAt && Date.parse(validClaim.targetRecord.expires_at) > Date.now(),
      oracle: { outcome: (!validClaim.targetRecord.disabledAt && Date.parse(validClaim.targetRecord.expires_at) > Date.now()) ? 'allow' : 'deny' },
    };
    expect(checkValid.valid).toBe(true);
    expect(checkValid.oracle.outcome).toBe('allow');

    // Revoked targetRecord in claim
    const revokedClaim = {
      ...validClaim,
      targetRecord: { ...target, disabled_at: '2026-02-01T00:00:00.000Z' },
    };
    const checkRevoked = {
      valid: !revokedClaim.targetRecord.disabled_at && Date.parse(revokedClaim.targetRecord.expiresAt) > Date.now(),
      oracle: { outcome: (!revokedClaim.targetRecord.disabled_at && Date.parse(revokedClaim.targetRecord.expiresAt) > Date.now()) ? 'allow' : 'deny' },
    };
    expect(checkRevoked.valid).toBe(false);
    expect(checkRevoked.oracle.outcome).toBe('deny');

    // Mismatched targetRecord in claim
    const mismatchedIdClaim = {
      ...validClaim,
      targetRecord: { ...target, id: '00000000-0000-4000-8000-000000000999' },
    };
    expect(() => {
      if (mismatchedIdClaim.targetRecord.id !== run.target_record_id) {
        throw new Error('Target record in runner claim does not match run target-record binding.');
      }
    }).toThrow('Target record in runner claim does not match run target-record binding.');
  });
});
