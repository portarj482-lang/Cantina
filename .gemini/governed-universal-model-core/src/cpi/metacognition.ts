import type { CpiAssessment, OperationalSelfModel } from "./types.ts";

export function inspectOperationalSelf(self: OperationalSelfModel): CpiAssessment {
  const findings: string[] = [];
  const uncertainty: string[] = [];
  const requiredEvidence: string[] = [];
  if (!self.version.trim()) findings.push("Self-model version is missing.");
  if (!self.policyVersion.trim()) findings.push("Policy version is missing.");
  if (self.capabilities.length === 0) uncertainty.push("No capabilities are declared.");
  if (self.limitations.length === 0) findings.push("Limitations are not declared; self-description is incomplete.");
  if (self.activePermissions.length === 0) uncertainty.push("No active permissions are declared; verify whether this means no permissions or missing data.");
  if (!self.lastVerifiedAt) requiredEvidence.push("Independent verification record for the operational self-model");
  if (self.evidenceIds.length === 0) requiredEvidence.push("Evidence supporting capability, limitation, and permission declarations");
  const severe = findings.length > 0;
  return {
    subjectId: `self-model:${self.version || "unknown"}`,
    disposition: severe ? "escalate" : requiredEvidence.length || uncertainty.length ? "abstain" : "recommend",
    findings,
    uncertainty,
    requiredEvidence,
    requiresIndependentReview: severe || requiredEvidence.length > 0,
  };
}
