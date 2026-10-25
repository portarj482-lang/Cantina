import { GovernedModelCore } from "./core.ts";
import type { ModelDefinition } from "./types.ts";

const core = new GovernedModelCore();
const common = {
  domain: "illustrative",
  description: "Demo model used to show governed model transitions.",
  invariantIds: ["identity-lineage", "governance-non-bypass", "auditability"],
  parentModelIds: [],
  declaredLossiness: "unknown" as const,
  approved: true,
};
const a: ModelDefinition = { ...common, id: "model-A", version: "1.0.0", semantics: "Example source semantics.", adapterId: "adapter-A" };
const b: ModelDefinition = { ...common, id: "model-B", version: "1.0.0", semantics: "Example target semantics.", adapterId: "adapter-B", parentModelIds: ["model-A@1.0.0"] };
core.registry.register(a);
core.registry.register(b);
const proposal = core.propose({
  sourceModelId: "model-A@1.0.0",
  targetModelId: "model-B@1.0.0",
  requestedBy: "demo-user",
  purpose: "Improve model interoperability while preserving auditability.",
  riskTier: "moderate",
  preservationClaims: ["identity-lineage", "governance-non-bypass", "auditability"],
  evidenceRefs: ["demo:test-fixture"],
  ethicalAssessment: {
    purpose: "Improve interoperability for a toy demonstration.",
    affectedParties: ["demo users"],
    foreseeableBenefits: ["Clearer model interoperability"],
    foreseeableHarms: ["Incorrect mappings could misrepresent semantics"],
    rightsAndDuties: ["Do not misrepresent a transformation as lossless without evidence"],
    alternativesConsidered: ["Keep models separate", "Use a one-way mapping"],
    mitigations: ["Require adapter-specific round-trip tests before claiming reversibility"],
    uncertainty: ["No production semantics or adapter code is included"],
    reviewer: "demo-reviewer",
    status: "approved",
    rationale: "Illustrative low-impact example; not a real-world ethics certification.",
  },
});
console.log(JSON.stringify({ proposal, decision: core.evaluate(proposal), audit: core.getAuditTrail() }, null, 2));
