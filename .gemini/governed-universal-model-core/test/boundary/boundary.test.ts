import test from "node:test";
import assert from "node:assert/strict";
import { BoundaryService, hashBoundaryPayload } from "../../src/boundary/index.ts";

function captured(service: BoundaryService, extra: { ambiguityReasons?: string[]; unknownFields?: string[]; evidenceIds?: string[] } = {}) {
  return service.capture({
    id: "record-1", projectId: "project-a", kind: "hypothesis", payload: { claim: "revoked owner rejected" },
    sourceType: "git", sourceLocator: "src/Wallet.sol", sourceRevision: "abc123", capturedBy: "agent-a",
    ...extra,
  });
}

test("capture preserves provenance and does not admit the record", () => {
  const service = new BoundaryService();
  const record = captured(service);
  assert.equal(record.status, "captured");
  assert.equal(record.provenance.contentSha256, hashBoundaryPayload({ claim: "revoked owner rejected" }));
  assert.equal(record.provenance.sourceRevision.state, "known");
});

test("missing source revision or unknown fields quarantine captured input", () => {
  const service = new BoundaryService();
  const record = service.capture({ projectId: "p", kind: "claim", payload: { a: 1 }, sourceType: "agent", sourceLocator: "task/1", capturedBy: "agent-a" });
  assert.equal(record.status, "quarantined");
  assert.equal(record.provenance.sourceRevision.state, "unknown");
  assert.throws(() => service.verify("p", record.id, "tester", ["e1"], "abc"), /unknown or does not match/);
});

test("quarantined records cannot be verified while ambiguity remains", () => {
  const service = new BoundaryService();
  const record = captured(service, { ambiguityReasons: ["conflicting source definitions"], evidenceIds: ["e1"] });
  assert.equal(record.status, "quarantined");
  assert.throws(() => service.verify("project-a", record.id, "tester", ["e1"], "abc123"), /Unresolved unknown fields or ambiguity/);
});

test("verification requires matching revision and evidence", () => {
  const service = new BoundaryService();
  const record = captured(service);
  assert.throws(() => service.verify("project-a", record.id, "tester", [], "abc123"), /requires evidence/);
  assert.throws(() => service.verify("project-a", record.id, "tester", ["e1"], "wrong"), /does not match/);
  const verified = service.verify("project-a", record.id, "tester", ["e1"], "abc123");
  assert.equal(verified.status, "verified");
});

test("admission fails closed without independent reviewer, attached evidence, and passing required checks", () => {
  const service = new BoundaryService();
  const record = captured(service);
  service.verify("project-a", record.id, "tester", ["e1"], "abc123");
  const base = { actor: "agent-a", reviewer: "reviewer-b", reason: "Reviewed evidence", policyVersion: "p1", evidenceIds: ["e1"], checks: [{ name: "source", passed: true }], requiredChecks: ["source", "negative-control"], expectedSourceRevision: "abc123" };
  assert.throws(() => service.admit("project-a", record.id, { ...base, reviewer: "agent-a" }), /must differ/);
  assert.throws(() => service.admit("project-a", record.id, base), /missing or failed: negative-control/);
  assert.throws(() => service.admit("project-a", record.id, { ...base, evidenceIds: ["e2"], checks: [{ name: "source", passed: true }, { name: "negative-control", passed: true }] }), /attached to the verified record/);
});

test("admission succeeds only after required checks and independent review", () => {
  const service = new BoundaryService();
  const record = captured(service);
  service.verify("project-a", record.id, "tester", ["e1", "e2"], "abc123");
  const admitted = service.admit("project-a", record.id, {
    actor: "agent-a", reviewer: "human-reviewer", reason: "All gates passed", policyVersion: "p1", evidenceIds: ["e1", "e2"],
    checks: [{ name: "source", passed: true }, { name: "reproduction", passed: true }], requiredChecks: ["source", "reproduction"], expectedSourceRevision: "abc123",
  });
  assert.equal(admitted.status, "admitted");
  assert.equal(admitted.version, 3);
});

test("project isolation and audit history are enforced", () => {
  const service = new BoundaryService();
  const record = captured(service);
  assert.throws(() => service.get("project-b", record.id), /not found/);
  assert.equal(service.audit("project-a").length, 1);
  assert.equal(service.audit("project-b").length, 0);
});
