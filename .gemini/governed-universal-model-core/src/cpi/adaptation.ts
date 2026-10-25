import type { GovernanceDecision } from "../types.ts";

export interface SandboxChangeRequest {
  id: string;
  changeDescription: string;
  artifactDigest: string;
  testsPassed: boolean;
  invariantChecksPassed: boolean;
  riskTier: "low" | "moderate" | "high" | "critical";
}

export interface IndependentApproval {
  requestId: string;
  approverId: string;
  approvedArtifactDigest: string;
  policyVersion: string;
  expiresAt: string;
  signatureRef: string;
}

export interface SandboxAdapter {
  applyToIsolatedSandbox(request: SandboxChangeRequest): Promise<{ sandboxId: string; resultDigest: string }>;
}

/** No live-state operation exists here. The caller must provide a separately issued approval. */
export async function applyApprovedSandboxChange(
  request: SandboxChangeRequest,
  governance: GovernanceDecision,
  approval: IndependentApproval | undefined,
  sandbox: SandboxAdapter,
): Promise<{ sandboxId: string; resultDigest: string }> {
  if (governance.decision !== "allow") throw new Error("Governance decision does not allow the change");
  if (request.riskTier === "high" || request.riskTier === "critical") throw new Error("High/critical changes require a separate reviewed workflow; this adapter is low/moderate-risk only");
  if (!request.testsPassed || !request.invariantChecksPassed) throw new Error("Tests and invariant checks must pass before sandbox application");
  if (!approval) throw new Error("Independent approval is required before sandbox application");
  if (approval.requestId !== request.id || approval.approvedArtifactDigest !== request.artifactDigest) throw new Error("Approval does not match request and artifact digest");
  if (Date.parse(approval.expiresAt) <= Date.now()) throw new Error("Approval has expired");
  if (!approval.approverId.trim() || !approval.signatureRef.trim() || !approval.policyVersion.trim()) throw new Error("Approval provenance is incomplete");
  return sandbox.applyToIsolatedSandbox(structuredClone(request));
}
