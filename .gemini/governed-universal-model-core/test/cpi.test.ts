import test from "node:test";
import assert from "node:assert/strict";
import { proposeAuthorizationInvariants } from "../src/security/contract-adapter.ts";
import { applyApprovedSandboxChange, observeModel, interpretObservation, assessCompatibility, inspectOperationalSelf } from "../src/cpi/index.ts";
import type { OperationalSelfModel } from "../src/cpi/index.ts";
import type { GovernanceDecision } from "../src/types.ts";

test("perception records only explicit facts and retains unknowns", () => {
  const observation = observeModel({ subjectId: "model-a", source: "fixture", facts: [{ key: "kind", value: "graph" }], unknowns: ["edge semantics"] });
  const interpretation = interpretObservation(observation);
  assert.deepEqual(interpretation.concepts, ["kind"]);
  assert.deepEqual(interpretation.unresolvedQuestions, ["edge semantics"]);
  assert.equal(interpretation.relationships.length, 0);
});

test("compatibility abstains when no required invariants were provided", () => {
  const report = assessCompatibility({ sourceModelId: "a@1", targetModelId: "b@1", sourceInvariantIds: [], targetInvariantIds: [], requiredInvariantIds: [], reversibility: "unknown" });
  assert.equal(report.compatible, "undetermined");
  assert.equal(report.disposition, "abstain");
});

test("compatibility rejects missing required invariants", () => {
  const report = assessCompatibility({ sourceModelId: "a@1", targetModelId: "b@1", sourceInvariantIds: ["identity"], targetInvariantIds: [], requiredInvariantIds: ["identity"], reversibility: "exact-proven" });
  assert.equal(report.compatible, false);
  assert.deepEqual(report.missingInvariants, ["identity"]);
});

test("self-inspection requires evidence when not independently verified", () => {
  const self: OperationalSelfModel = { version: "0.1", capabilities: ["observe"], limitations: ["no live execution"], activePermissions: [], knownFailureModes: ["incomplete input"], policyVersion: "p1", evidenceIds: [] };
  const result = inspectOperationalSelf(self);
  assert.equal(result.disposition, "abstain");
  assert.equal(result.requiresIndependentReview, true);
});

test("security adapter emits hypotheses, not confirmed findings", () => {
  const result = proposeAuthorizationInvariants({
    contractId: "C",
    sourceRevision: "test",
    functions: [{ signature: "withdraw(address,uint256)", externallyCallable: true }],
    stateTransitions: [{ name: "withdraw", preconditions: ["sufficient balance"], postconditions: ["balance decreases"] }],
    evidence: [{ id: "source-observation", kind: "observation", description: "Minimal fixture metadata", verified: false }],
  });

  assert.ok(result.length > 0, "Expected at least one result");
  const [candidate] = result;
  assert.ok(candidate, "Expected a candidate after non-empty result assertion");
  assert.equal(candidate.status, "hypothesis-only");
});

test("sandbox adaptation fails closed without independent approval", async () => {
  const governance: GovernanceDecision = { proposalId: "r1", decision: "allow", reasons: ["checks passed"], policyVersion: "p1", decidedAt: new Date().toISOString() };
  const request = { id: "r1", changeDescription: "test-only adapter update", artifactDigest: "sha256:abc", testsPassed: true, invariantChecksPassed: true, riskTier: "low" as const };
  const sandbox = { async applyToIsolatedSandbox() { return { sandboxId: "sb1", resultDigest: "sha256:result" }; } };
  await assert.rejects(() => applyApprovedSandboxChange(request, governance, undefined, sandbox), /Independent approval/);
});
