import { describe, expect, it } from 'vitest';
import { matchWorkflowToScope, type ScopeRecord } from '../src/policy/scope.js';
import type { WorkflowCreateInput } from '../src/schemas.js';

const base: WorkflowCreateInput = {
  targetRecordId: '00000000-0000-4000-8000-000000000002',
  programSlug: 'coinbase-cantina',
  repositoryUrl: 'https://github.com/example/repo',
  sourceCommit: 'a'.repeat(40),
  chainId: 8453,
  targetAddresses: ['0x1111111111111111111111111111111111111111'],
  forkBlock: 123,
  requestedMethods: ['local-test', 'fork-test'],
  findingId: 'F-001',
  title: 'F-001 verification workflow',
};
const scope: ScopeRecord = {
  id: '00000000-0000-4000-8000-000000000001',
  programSlug: 'coinbase-cantina',
  repositoryUrl: 'https://github.com/example/repo.git/',
  sourceCommit: 'A'.repeat(40),
  chainId: 8453,
  targetAddresses: ['0x1111111111111111111111111111111111111111'],
  requiredForkBlock: 123,
  allowedMethods: ['local-test', 'fork-test'],
  programAuthorizationRef: 'verified-policy-reference',
  expiresAt: '2030-01-01T00:00:00.000Z',
  restrictions: {},
};

describe('fail-closed scope policy', () => {
  it('accepts only an exact approved repository, commit, chain, block, address, and method subset', () => {
    expect(matchWorkflowToScope(base, scope, new Date('2026-01-01T00:00:00Z'))).toEqual({ ok: true, scopeId: scope.id });
  });
  it('rejects unregistered scopes', () => {
    expect(matchWorkflowToScope(base, undefined).ok).toBe(false);
  });
  it('rejects mismatched commit, fork block, address, and unapproved method', () => {
    expect(matchWorkflowToScope({ ...base, sourceCommit: 'b'.repeat(40) }, scope).ok).toBe(false);
    expect(matchWorkflowToScope({ ...base, forkBlock: 124 }, scope).ok).toBe(false);
    expect(matchWorkflowToScope({ ...base, targetAddresses: ['0x2222222222222222222222222222222222222222'] }, scope).ok).toBe(false);
    expect(matchWorkflowToScope({ ...base, requestedMethods: ['symbolic-analysis'] }, scope).ok).toBe(false);
  });
  it('rejects expired authorization', () => {
    expect(matchWorkflowToScope(base, { ...scope, expiresAt: '2020-01-01T00:00:00Z' }, new Date('2026-01-01T00:00:00Z')).ok).toBe(false);
  });
});
