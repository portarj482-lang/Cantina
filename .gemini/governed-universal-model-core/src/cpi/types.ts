export type ConfidenceBand = "low" | "moderate" | "high";
export type Reversibility = "exact-proven" | "conditional" | "lossy" | "unknown";
export type CpiDisposition = "recommend" | "abstain" | "reject" | "escalate";

export interface EvidenceItem {
  id: string;
  kind: "source" | "test" | "formal-proof" | "human-review" | "observation";
  description: string;
  digest?: string;
  verified: boolean;
}

export interface ModelObservation {
  subjectId: string;
  observedAt: string;
  source: string;
  facts: Array<{ key: string; value: string | number | boolean; evidenceId?: string }>;
  unknowns: string[];
}

export interface CognitiveHypothesis {
  id: string;
  claim: string;
  confidence: ConfidenceBand;
  basis: string[];
  counterevidence: string[];
  status: "unverified" | "supported" | "contradicted";
}

export interface SemanticInterpretation {
  subjectId: string;
  summary: string;
  concepts: string[];
  relationships: Array<{ from: string; relation: string; to: string }>;
  assumptions: string[];
  unresolvedQuestions: string[];
  evidenceIds: string[];
}

export interface CompatibilityReport {
  sourceModelId: string;
  targetModelId: string;
  compatible: boolean | "undetermined";
  preservedInvariants: string[];
  missingInvariants: string[];
  conflicts: string[];
  reversibility: Reversibility;
  evidenceIds: string[];
  disposition: CpiDisposition;
}

export interface OperationalSelfModel {
  version: string;
  capabilities: string[];
  limitations: string[];
  activePermissions: string[];
  knownFailureModes: string[];
  policyVersion: string;
  lastVerifiedAt?: string;
  evidenceIds: string[];
}

export interface CpiAssessment {
  subjectId: string;
  disposition: CpiDisposition;
  findings: string[];
  uncertainty: string[];
  requiredEvidence: string[];
  requiresIndependentReview: boolean;
}
