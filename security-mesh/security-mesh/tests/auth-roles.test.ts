import { describe, expect, it } from 'vitest';
import {
  checkFindingApprovalSeparation,
  checkIndependentReviewSeparation,
  checkSubmissionAuthorization,
  checkRunnerPermissionBoundary,
  type AuthenticatedPrincipal,
} from '../src/security/roles.js';

describe('Role Boundaries and Separation of Duties', () => {
  const researcherPrincipal: AuthenticatedPrincipal = {
    id: 'researcher:alice',
    role: 'researcher',
    actorLabel: 'alice',
    authenticatedAt: new Date().toISOString(),
  };

  const approverPrincipal: AuthenticatedPrincipal = {
    id: 'approver:bob',
    role: 'approver',
    actorLabel: 'bob',
    authenticatedAt: new Date().toISOString(),
  };

  const selfApproverPrincipal: AuthenticatedPrincipal = {
    id: 'approver:alice',
    role: 'approver',
    actorLabel: 'alice',
    authenticatedAt: new Date().toISOString(),
  };

  const reviewerPrincipal: AuthenticatedPrincipal = {
    id: 'reviewer:carol',
    role: 'reviewer',
    actorLabel: 'carol',
    authenticatedAt: new Date().toISOString(),
  };

  const runnerPrincipal: AuthenticatedPrincipal = {
    id: 'runner:node-1',
    role: 'runner',
    actorLabel: 'node-1',
    authenticatedAt: new Date().toISOString(),
  };

  describe('Finding approval separation', () => {
    it('allows a distinct approver to approve a researcher finding', () => {
      const result = checkFindingApprovalSeparation('alice', approverPrincipal);
      expect(result.allowed).toBe(true);
    });

    it('denies a researcher approving their own finding (same actor label)', () => {
      const result = checkFindingApprovalSeparation('alice', selfApproverPrincipal);
      expect(result.allowed).toBe(false);
      expect(result.reason).toMatch(/cannot approve their own finding/i);
    });

    it('denies a non-approver role from approving findings', () => {
      const result = checkFindingApprovalSeparation('alice', reviewerPrincipal);
      expect(result.allowed).toBe(false);
      expect(result.reason).toMatch(/Role 'approver' is required/i);
    });
  });

  describe('Independent review separation', () => {
    it('allows an independent reviewer to review finding evidence', () => {
      const result = checkIndependentReviewSeparation('alice', reviewerPrincipal);
      expect(result.allowed).toBe(true);
    });

    it('denies a researcher conducting an independent review of their own finding', () => {
      const selfReviewer: AuthenticatedPrincipal = {
        id: 'reviewer:alice',
        role: 'reviewer',
        actorLabel: 'alice',
        authenticatedAt: new Date().toISOString(),
      };
      const result = checkIndependentReviewSeparation('alice', selfReviewer);
      expect(result.allowed).toBe(false);
      expect(result.reason).toMatch(/must be a distinct identity/i);
    });
  });

  describe('Submission authorization boundary', () => {
    it('allows an approver to authorize external submission for a finding researched by someone else', () => {
      const result = checkSubmissionAuthorization(approverPrincipal, 'alice');
      expect(result.allowed).toBe(true);
    });

    it('denies submission authorization if the approver is the researcher', () => {
      const result = checkSubmissionAuthorization(selfApproverPrincipal, 'alice');
      expect(result.allowed).toBe(false);
      expect(result.reason).toMatch(/cannot authorize submission/i);
    });

    it('denies reviewers and runners from authorizing submissions', () => {
      expect(checkSubmissionAuthorization(reviewerPrincipal, 'alice').allowed).toBe(false);
      expect(checkSubmissionAuthorization(runnerPrincipal, 'alice').allowed).toBe(false);
    });
  });

  describe('Runner permission boundary', () => {
    it('allows runner to claim runs and upload artifacts', () => {
      expect(checkRunnerPermissionBoundary(runnerPrincipal, 'claim_run').allowed).toBe(true);
      expect(checkRunnerPermissionBoundary(runnerPrincipal, 'upload_artifact').allowed).toBe(true);
    });

    it('denies runner from creating scopes or approving runs', () => {
      expect(checkRunnerPermissionBoundary(runnerPrincipal, 'create_scope').allowed).toBe(false);
      expect(checkRunnerPermissionBoundary(runnerPrincipal, 'approve_run').allowed).toBe(false);
      expect(checkRunnerPermissionBoundary(runnerPrincipal, 'evaluate_gate').allowed).toBe(false);
    });

    it('denies non-runners from claiming runs or uploading artifacts directly', () => {
      expect(checkRunnerPermissionBoundary(researcherPrincipal, 'claim_run').allowed).toBe(false);
      expect(checkRunnerPermissionBoundary(approverPrincipal, 'upload_artifact').allowed).toBe(false);
    });
  });
});
