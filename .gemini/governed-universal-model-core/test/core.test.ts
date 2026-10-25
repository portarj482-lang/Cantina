import test from "node:test";
import assert from "node:assert/strict";
import { GovernedModelCore } from "../src/core.ts";
import type { ModelDefinition, TransformationProposal } from "../src/types.ts";

const base = (id: string): ModelDefinition => ({
  id, version: "1.0.0", domain: "test", description: "test model", semantics: "test semantics",
  invariantIds: ["identity-lineage", "governance-non-bypass", "auditability"], parentModelIds: [],
  adapterId: `adapter-${id}`, declaredLossiness: "unknown", approved: true,
});
const proposal = (overrides: Partial<Omit<TransformationProposal, "id" | "requestedAt">> = {}) => ({
  sourceModelId: "A@1.0.0", targetModelId: "B@1.0.0", requestedBy: "tester",
  purpose: "Preserve integrity while improving interoperability", riskTier: "moderate" as const,
  preservationClaims: ["identity-lineage", "governance-non-bypass", "auditability"], evidenceRefs: ["test:evidence"],
  ethicalAssessment: { purpose: "test", affectedParties: ["users"], foreseeableBenefits: ["clarity"], foreseeableHarms: ["misrepresentation"], rightsAndDuties: ["honesty"], alternativesConsidered: ["no change"], mitigations: ["tests"], uncertainty: ["unknown mapping semantics"], reviewer: "independent-reviewer", status: "approved" as const, rationale: "test rationale" },
  ...overrides,
});

test("unknown target fails closed", () => {
  const core = new GovernedModelCore(); core.registry.register(base("A"));
  const p = core.propose(proposal());
  const d = core.evaluate(p);
  assert.equal(d.decision, "deny");
  assert.ok(d.reasons.some(r => r.includes("Unknown target model")));
});

test("high-risk change requires human authorization", () => {
  const core = new GovernedModelCore(); core.registry.register(base("A")); core.registry.register(base("B"));
  const p = core.propose(proposal({ riskTier: "high" }));
  const d = core.evaluate(p);
  assert.equal(d.decision, "needs-human-review");
});

test("missing constitutional invariant claim is denied", () => {
  const core = new GovernedModelCore(); core.registry.register(base("A")); core.registry.register(base("B"));
  const p = core.propose(proposal({ preservationClaims: ["auditability"] }));
  const d = core.evaluate(p);
  assert.equal(d.decision, "deny");
  assert.ok(d.reasons.some(r => r.includes("Required invariant preservation claims missing")));
});

test("audit trail records proposal and evaluation", () => {
  const core = new GovernedModelCore(); core.registry.register(base("A")); core.registry.register(base("B"));
  const p = core.propose(proposal()); core.evaluate(p);
  assert.equal(core.getAuditTrail().length, 2);
});
