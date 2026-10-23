import type { OracleDecision } from './target-record.js';

export function bindEvidenceToTarget(expectedTargetRecordId: string, artifactTargetRecordId: string | null | undefined): OracleDecision {
  const reasons = !expectedTargetRecordId || !artifactTargetRecordId || expectedTargetRecordId !== artifactTargetRecordId
    ? ['Evidence artifact target-record binding is missing or mismatched.'] : [];
  return { oracleId: 'evidence-review-oracle', outcome: reasons.length ? 'deny' : 'allow', reasons };
}

export function validateIndependentHumanReview(workflowCreator: string, reviewerId: string, approverId?: string | string[]): OracleDecision {
  const reasons: string[] = [];
  if (!workflowCreator) reasons.push('Workflow creator is required to verify reviewer independence.');
  if (!reviewerId || reviewerId === workflowCreator) reasons.push('Reviewer must be a distinct human actor from the workflow creator.');
  const approvers = Array.isArray(approverId) ? approverId : (approverId ? [approverId] : []);
  if (approvers.some((id) => id === reviewerId)) reasons.push('Review and submission/run approval must remain separate decisions.');
  return { oracleId: 'evidence-review-oracle', outcome: reasons.length ? 'deny' : 'allow', reasons };
}

export function validateSeparateSubmissionApproval(reviewerId: string, submissionApproverId: string, workflowCreator?: string): OracleDecision {
  const reasons: string[] = [];
  if (!reviewerId) reasons.push('A verified independent reviewer is required before submission approval.');
  if (!submissionApproverId || submissionApproverId === reviewerId) reasons.push('Submission approval must be performed by a distinct human actor from the reviewer.');
  if (workflowCreator && submissionApproverId === workflowCreator) reasons.push('Submission approval cannot be performed by the workflow creator.');
  return { oracleId: 'evidence-review-oracle', outcome: reasons.length ? 'deny' : 'allow', reasons };
}

export function validateEvidencePreservation(
  decision: 'supported' | 'rejected' | 'inconclusive',
  evidenceRecords: Array<{ verified: boolean; outcome?: string }>,
): OracleDecision {
  const reasons: string[] = [];
  if (decision === 'supported') {
    if (!evidenceRecords.length) reasons.push('Supported finding must reference verified evidence records.');
    if (evidenceRecords.some((e) => !e.verified)) reasons.push('Supported finding cannot reference unverified evidence.');
    if (evidenceRecords.some((e) => e.outcome === 'failed' || e.outcome === 'rejected')) reasons.push('Supported finding cannot contradict negative evidence findings.');
  }
  return { oracleId: 'evidence-review-oracle', outcome: reasons.length ? 'deny' : 'allow', reasons };
}
