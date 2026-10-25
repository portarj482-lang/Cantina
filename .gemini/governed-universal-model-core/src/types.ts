export type RiskTier = "low" | "moderate" | "high" | "critical";
export type ReviewStatus = "not-reviewed" | "needs-review" | "approved" | "rejected";
export type Decision = "allow" | "deny" | "needs-human-review";

export interface ModelInvariant {
  id: string;
  description: string;
  severity: "required" | "recommended";
  validationMethod: string;
}

export interface ModelDefinition {
  id: string;
  version: string;
  domain: string;
  description: string;
  semantics: string;
  invariantIds: string[];
  parentModelIds: string[];
  adapterId: string;
  declaredLossiness: "none-claimed" | "lossy" | "unknown";
  approved: boolean;
}

export interface EthicalAssessment {
  purpose: string;
  affectedParties: string[];
  foreseeableBenefits: string[];
  foreseeableHarms: string[];
  rightsAndDuties: string[];
  alternativesConsidered: string[];
  mitigations: string[];
  uncertainty: string[];
  reviewer: string;
  status: ReviewStatus;
  rationale: string;
}

export interface TransformationProposal {
  id: string;
  sourceModelId: string;
  targetModelId: string;
  requestedBy: string;
  purpose: string;
  riskTier: RiskTier;
  preservationClaims: string[];
  evidenceRefs: string[];
  ethicalAssessment?: EthicalAssessment;
  requestedAt: string;
}

export interface GovernanceDecision {
  proposalId: string;
  decision: Decision;
  reasons: string[];
  policyVersion: string;
  decidedAt: string;
}

export interface AuditEvent {
  id: string;
  at: string;
  actor: string;
  action: string;
  subjectId: string;
  details: Record<string, unknown>;
}
