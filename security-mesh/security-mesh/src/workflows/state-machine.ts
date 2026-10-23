import type { WorkflowStatus } from '../types.js';

const transitions: Readonly<Record<WorkflowStatus, readonly WorkflowStatus[]>> = {
  queued: ['scope_check', 'cancelled', 'failed'],
  scope_check: ['learning', 'blocked', 'failed', 'cancelled'],
  learning: ['analysis', 'blocked', 'failed', 'cancelled'],
  analysis: ['approval_pending', 'inconclusive', 'blocked', 'failed', 'cancelled'],
  approval_pending: ['execution', 'blocked', 'cancelled'],
  execution: ['evidence_review', 'failed', 'timed_out', 'inconclusive', 'cancelled'],
  evidence_review: ['impact_review', 'analysis', 'inconclusive', 'rejected', 'cancelled'],
  impact_review: ['independent_review', 'analysis', 'inconclusive', 'rejected', 'cancelled'],
  independent_review: ['report_draft', 'analysis', 'rejected', 'inconclusive', 'cancelled'],
  report_draft: ['human_approval', 'analysis', 'rejected', 'cancelled'],
  human_approval: ['submitted', 'rejected', 'cancelled'],
  submitted: [],
  blocked: ['scope_check', 'cancelled'],
  failed: ['queued', 'cancelled'],
  timed_out: ['queued', 'cancelled'],
  inconclusive: ['analysis', 'cancelled'],
  rejected: ['analysis', 'cancelled'],
  cancelled: [],
};

export function canTransition(from: WorkflowStatus, to: WorkflowStatus): boolean {
  return transitions[from].includes(to);
}

export function assertTransition(from: WorkflowStatus, to: WorkflowStatus): void {
  if (!canTransition(from, to)) throw new Error(`Invalid workflow transition: ${from} -> ${to}`);
}
