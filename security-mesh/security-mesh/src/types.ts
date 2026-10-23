export type ExecutionStatus = 'queued' | 'running' | 'passed' | 'failed' | 'timed_out' | 'cancelled';
export type FindingStatus = 'unverified' | 'supported' | 'rejected' | 'inconclusive';
export type ReviewStatus = 'pending' | 'accepted' | 'challenged' | 'rejected';
export type ApprovalStatus = 'not_requested' | 'pending' | 'approved' | 'denied';
export type SubmissionStatus = 'not_ready' | 'drafted' | 'submitted' | 'acknowledged';
export type WorkflowStatus =
  | 'queued' | 'scope_check' | 'learning' | 'analysis' | 'approval_pending' | 'execution'
  | 'evidence_review' | 'impact_review' | 'independent_review' | 'report_draft'
  | 'human_approval' | 'submitted' | 'blocked' | 'failed' | 'timed_out'
  | 'inconclusive' | 'rejected' | 'cancelled';

export type GateOutcome = 'passed' | 'failed' | 'inconclusive' | 'not_applicable';

export interface AssertionResult {
  id: string;
  outcome: 'passed' | 'failed' | 'skipped';
  detail?: string;
}

export interface ArtifactReceipt {
  name: string;
  uri: string;
  sha256: string;
  mediaType: string;
  byteLength: number;
}

/** Receipt schema used between a separately deployed runner and the evidence service. */
export interface ExecutionReceipt {
  schemaVersion: 1;
  signatureAlgorithm?: 'hmac-sha256' | 'ed25519';
  runId: string;
  targetRecordId: string;
  runnerId: string;
  suiteId: string;
  repositoryUrl: string;
  sourceCommit: string;
  chainId: number;
  forkBlock: number;
  commandProfileId: string;
  toolVersions: Record<string, string>;
  exitCode: number;
  timedOut: boolean;
  assertions: AssertionResult[];
  logArtifact: ArtifactReceipt;
  artifacts: ArtifactReceipt[];
  startedAt: string;
  completedAt: string;
  signature: string;
}
