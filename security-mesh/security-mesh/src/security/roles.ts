export type Role = 'researcher' | 'reviewer' | 'approver' | 'administrator' | 'runner';

export interface AuthenticatedPrincipal {
  id: string;
  role: Role;
  actorLabel?: string | undefined;
  authenticatedAt: string;
}

export interface SeparationOfDutiesResult {
  allowed: boolean;
  reason?: string;
}

/**
 * Enforces separation of duties between finding research, review, and approval.
 */
export function checkFindingApprovalSeparation(
  researcherActor: string,
  approverPrincipal: AuthenticatedPrincipal
): SeparationOfDutiesResult {
  if (approverPrincipal.role !== 'approver') {
    return {
      allowed: false,
      reason: `Principal role '${approverPrincipal.role}' is not authorized to approve findings. Role 'approver' is required.`,
    };
  }

  const normalizedResearcher = researcherActor.toLowerCase().trim();
  const normalizedApprover = approverPrincipal.id.toLowerCase().trim();
  const normalizedApproverLabel = approverPrincipal.actorLabel?.toLowerCase().trim();

  if (
    normalizedApprover === normalizedResearcher ||
    (normalizedApproverLabel && normalizedApproverLabel === normalizedResearcher)
  ) {
    return {
      allowed: false,
      reason: 'Separation of duties violation: A researcher cannot approve their own finding.',
    };
  }

  return { allowed: true };
}

/**
 * Enforces separation of duties for independent review (Gate G8 / review stage).
 */
export function checkIndependentReviewSeparation(
  researcherActor: string,
  reviewerPrincipal: AuthenticatedPrincipal
): SeparationOfDutiesResult {
  if (reviewerPrincipal.role !== 'reviewer' && reviewerPrincipal.role !== 'approver') {
    return {
      allowed: false,
      reason: `Principal role '${reviewerPrincipal.role}' cannot conduct independent reviews. Role 'reviewer' or 'approver' is required.`,
    };
  }

  const normalizedResearcher = researcherActor.toLowerCase().trim();
  const normalizedReviewer = reviewerPrincipal.id.toLowerCase().trim();
  const normalizedReviewerLabel = reviewerPrincipal.actorLabel?.toLowerCase().trim();

  if (
    normalizedReviewer === normalizedResearcher ||
    (normalizedReviewerLabel && normalizedReviewerLabel === normalizedResearcher)
  ) {
    return {
      allowed: false,
      reason: 'Separation of duties violation: Independent reviewer must be a distinct identity from the researcher.',
    };
  }

  return { allowed: true };
}

/**
 * Enforces that only authorized approvers can record submission authorization.
 * Reviewers, administrators, and runners cannot authorize external submission.
 */
export function checkSubmissionAuthorization(
  approverPrincipal: AuthenticatedPrincipal,
  researcherActor?: string
): SeparationOfDutiesResult {
  if (approverPrincipal.role !== 'approver') {
    return {
      allowed: false,
      reason: `Only role 'approver' can authorize submission. Current role: '${approverPrincipal.role}'.`,
    };
  }

  if (researcherActor) {
    const normalizedResearcher = researcherActor.toLowerCase().trim();
    const normalizedApprover = approverPrincipal.id.toLowerCase().trim();
    const normalizedApproverLabel = approverPrincipal.actorLabel?.toLowerCase().trim();

    if (
      normalizedApprover === normalizedResearcher ||
      (normalizedApproverLabel && normalizedApproverLabel === normalizedResearcher)
    ) {
      return {
        allowed: false,
        reason: 'Separation of duties violation: Researcher cannot authorize submission of their own finding.',
      };
    }
  }

  return { allowed: true };
}

/**
 * Enforces that runners cannot create scopes, workflows, or human approvals.
 */
export function checkRunnerPermissionBoundary(
  principal: AuthenticatedPrincipal,
  action: 'create_scope' | 'approve_run' | 'evaluate_gate' | 'claim_run' | 'upload_artifact'
): SeparationOfDutiesResult {
  if (principal.role === 'runner') {
    if (action === 'claim_run' || action === 'upload_artifact') {
      return { allowed: true };
    }
    return {
      allowed: false,
      reason: `Runner role is strictly restricted to runner operations and cannot perform action '${action}'.`,
    };
  }

  if (action === 'claim_run' || action === 'upload_artifact') {
    return {
      allowed: false,
      reason: `Only role 'runner' can perform execution claims and artifact uploads. Current role: '${principal.role}'.`,
    };
  }

  return { allowed: true };
}
