import test from "node:test";
import assert from "node:assert/strict";
import { LamportClock, SimulationClock, HashLinkedTemporalAudit, TemporalMappingRegistry, utcCanonicalization } from "../src/temporal/index.ts";
import { planSolver } from "../src/cci/index.ts";
import type { ComplexityAssessment } from "../src/cci/index.ts";

test("Lamport clock increments locally", () => {
  const clock = new LamportClock("agent-a");
  assert.equal(clock.tick(), 1);
  assert.equal(clock.tick(), 2);
});

test("Lamport clock observes remote counter and advances beyond it", () => {
  const clock = new LamportClock("agent-a");
  clock.tick();
  assert.equal(clock.observe(10), 11);
});

test("Lamport clock rejects invalid remote values", () => {
  const clock = new LamportClock("agent-a");
  assert.throws(() => clock.observe(-1));
  assert.throws(() => clock.observe(Number.POSITIVE_INFINITY));
});

test("simulation clock advances without wall-clock coupling", () => {
  const clock = new SimulationClock("sim-1", 4);
  assert.equal(clock.advance(3), 7);
  assert.equal(clock.now(), 7);
});

test("simulation clock can rewind only within simulation state", () => {
  const clock = new SimulationClock("sim-1", 10);
  assert.equal(clock.rewindTo(2), 2);
  assert.throws(() => clock.rewindTo(20));
  assert.throws(() => clock.advance(-1));
});

test("hash-linked audit validates intact chain", () => {
  const audit = new HashLinkedTemporalAudit();
  audit.append({ actor: "test", action: "created", subjectId: "s1", details: { b: 2, a: 1 } });
  audit.append({ actor: "test", action: "updated", subjectId: "s1", details: { ok: true } });
  assert.deepEqual(audit.verify(), { valid: true });
});

test("mapping registry requires assumptions and limitations", () => {
  const registry = new TemporalMappingRegistry();
  registry.register(utcCanonicalization);
  assert.deepEqual(registry.listIds(), ["utc-canonicalization-v1"]);
  assert.equal(registry.find("utc-instant", "utc-instant").length, 1);
  assert.throws(() => registry.register(utcCanonicalization));
});

test("CCI defers unknown complexity classification", () => {
  const assessment: ComplexityAssessment = {
    problemId: "custom-1", formulation: "unknown", classLabel: "unknown",
    evidence: [], inputSizeDescription: "unknown", status: "unknown", caveats: [],
  };
  assert.equal(planSolver(assessment, { budgetMs: 100 }).method, "defer");
});

test("CCI uses bounded search for exact NP-hard task with budget", () => {
  const assessment: ComplexityAssessment = {
    problemId: "fixture-sat", formulation: "decision", classLabel: "NP-complete",
    evidence: [{ kind: "literature", reference: "fixture reference", reviewed: true }],
    inputSizeDescription: "n variables", status: "established-result",
    timeBudgetMs: 50, caveats: ["Input label is supplied metadata."],
  };
  const plan = planSolver(assessment, { budgetMs: 1000, exactPreferred: true });
  assert.equal(plan.method, "bounded-search");
  assert.equal(plan.hardBudgetMs, 50);
  assert.equal(plan.requiresIndependentVerification, true);
});

test("CCI rejects non-positive budgets", () => {
  const assessment: ComplexityAssessment = {
    problemId: "x", formulation: "search", classLabel: "P", evidence: [],
    inputSizeDescription: "n", status: "hypothesis", caveats: [],
  };
  assert.throws(() => planSolver(assessment, { budgetMs: 0 }));
});


test("CCI rejects invalid assessment-specific resource budgets", () => {
  const assessment: ComplexityAssessment = {
    problemId: "bad-budget", formulation: "search", classLabel: "NP-hard", evidence: [],
    inputSizeDescription: "n", status: "hypothesis", caveats: [], timeBudgetMs: -1,
  };
  assert.throws(() => planSolver(assessment, { budgetMs: 100 }));
});

test("CCI does not claim to verify a supplied candidate", () => {
  const assessment: ComplexityAssessment = {
    problemId: "candidate", formulation: "verification", classLabel: "P", evidence: [],
    inputSizeDescription: "n", status: "hypothesis", caveats: [],
  };
  const plan = planSolver(assessment, { budgetMs: 100, verifiedCandidateAvailable: true });
  assert.equal(plan.method, "defer");
  assert.equal(plan.requiresIndependentVerification, true);
});
