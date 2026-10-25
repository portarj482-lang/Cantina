import { observeModel, interpretObservation, assessCompatibility, inspectOperationalSelf } from "./index.ts";

const observation = observeModel({
  subjectId: "example-graph@1",
  source: "demo-fixture",
  facts: [
    { key: "representation", value: "directed-graph", evidenceId: "fixture-001" },
    { key: "node-identity", value: "stable-id", evidenceId: "fixture-001" },
  ],
  unknowns: ["Whether parallel edges are semantically meaningful"],
});
console.log("Observation interpretation:", interpretObservation(observation));
console.log("Compatibility:", assessCompatibility({ sourceModelId: "graph@1", targetModelId: "relational@1", sourceInvariantIds: ["identity-lineage"], targetInvariantIds: ["identity-lineage"], requiredInvariantIds: ["identity-lineage"], reversibility: "unknown", evidenceIds: ["fixture-001"] }));
console.log("Self-inspection:", inspectOperationalSelf({ version: "0.2.0", capabilities: ["observe", "compare-declared-invariants"], limitations: ["does not infer missing facts", "does not execute transformations"], activePermissions: [], knownFailureModes: ["incomplete input", "incorrect declared invariants"], policyVersion: "constitution-0.1.0", evidenceIds: [] }));
