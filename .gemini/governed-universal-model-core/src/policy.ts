import type { EthicalAssessment, GovernanceDecision, TransformationProposal } from "./types.ts";

export interface GovernancePolicy {
  version: string;
  requireEvidenceFor: Array<TransformationProposal["riskTier"]>;
  requireHumanReviewFor: Array<TransformationProposal["riskTier"]>;
  requireEthicalAssessmentFor: Array<TransformationProposal["riskTier"]>;
  forbiddenPurposeTerms: string[];
  constitutionalInvariantIds: string[];
}

const HIGHER_RISK = new Set(["high", "critical"]);

export function assessEthics(input: EthicalAssessment | undefined): string[] {
  if (!input) return ["Ethical assessment is missing."];
  const issues: string[] = [];
  if (!input.purpose.trim()) issues.push("A stated purpose is required.");
  if (input.affectedParties.length === 0) issues.push("Affected parties must be considered; use an explicit 'none identified' rationale if appropriate.");
  if (input.foreseeableHarms.length === 0) issues.push("Foreseeable harms must be assessed, even if none are identified.");
  if (input.alternativesConsidered.length === 0) issues.push("At least one alternative, including taking no action, must be considered.");
  if (!input.rationale.trim()) issues.push("Ethical rationale is required.");
  if (!input.reviewer.trim()) issues.push("A reviewer identity is required.");
  if (input.status !== "approved") issues.push(`Ethical review status is '${input.status}', not 'approved'.`);
  return issues;
}

export function decide(
  proposal: TransformationProposal,
  knownModels: { sourceApproved: boolean; targetApproved: boolean; targetKnown: boolean },
  policy: GovernancePolicy,
  protectedInvariantIds: string[],
): GovernanceDecision {
  const reasons: string[] = [];
  if (!knownModels.targetKnown) reasons.push("Unknown target model: register and review its adapter before activation.");
  if (!knownModels.sourceApproved) reasons.push("Source model is not approved.");
  if (!knownModels.targetApproved) reasons.push("Target model is not approved.");
  if (proposal.sourceModelId === proposal.targetModelId) reasons.push("Source and target must differ for a transformation proposal.");
  if (proposal.preservationClaims.length === 0) reasons.push("No preservation claims were supplied.");
  if (policy.requireEvidenceFor.includes(proposal.riskTier) && proposal.evidenceRefs.length === 0) {
    reasons.push(`Evidence references are required for ${proposal.riskTier}-risk proposals.`);
  }
  if (policy.requireEthicalAssessmentFor.includes(proposal.riskTier)) {
    reasons.push(...assessEthics(proposal.ethicalAssessment));
  }
  const purpose = proposal.purpose.toLowerCase();
  for (const term of policy.forbiddenPurposeTerms) {
    if (term.trim() && purpose.includes(term.toLowerCase())) reasons.push(`Purpose matched a prohibited-purpose policy term: '${term}'.`);
  }

  const missingProtectedClaims = protectedInvariantIds.filter(id => !proposal.preservationClaims.includes(id));
  if (missingProtectedClaims.length) reasons.push(`Required invariant preservation claims missing: ${missingProtectedClaims.join(", ")}.`);

  if (reasons.length > 0) {
    const requiresHuman = policy.requireHumanReviewFor.includes(proposal.riskTier) &&
      !reasons.some(r => r.startsWith("Unknown target model") || r.includes("not approved") || r.includes("prohibited-purpose") || r.includes("preservation claims missing"));
    return {
      proposalId: proposal.id,
      decision: requiresHuman ? "needs-human-review" : "deny",
      reasons,
      policyVersion: policy.version,
      decidedAt: new Date().toISOString(),
    };
  }

  if (policy.requireHumanReviewFor.includes(proposal.riskTier)) {
    return {
      proposalId: proposal.id,
      decision: "needs-human-review",
      reasons: [`${proposal.riskTier}-risk transformation requires independent human authorization.`],
      policyVersion: policy.version,
      decidedAt: new Date().toISOString(),
    };
  }

  return { proposalId: proposal.id, decision: "allow", reasons: ["Declared policy checks passed; this is not a guarantee of moral correctness."], policyVersion: policy.version, decidedAt: new Date().toISOString() };
}

export const defaultPolicy: GovernancePolicy = {
  version: "constitution-0.1.0",
  requireEvidenceFor: ["moderate", "high", "critical"],
  requireHumanReviewFor: ["high", "critical"],
  requireEthicalAssessmentFor: ["moderate", "high", "critical"],
  forbiddenPurposeTerms: ["bypass authorization", "conceal harm", "evade oversight"],
  constitutionalInvariantIds: ["identity-lineage", "governance-non-bypass", "auditability"],
};
