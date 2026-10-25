import test from "node:test";
import assert from "node:assert/strict";
import {
  evaluateTemporalTransition,
  utcCanonicalization,
  validateTemporalValue,
  type TemporalValue,
} from "../src/temporal/index.ts";

const utc: TemporalValue = {
  basis: "utc-instant",
  value: "2026-10-25T12:00:00-07:00",
  source: "test-fixture",
};

test("validates UTC instant with explicit timezone", () => {
  assert.deepEqual(validateTemporalValue(utc), []);
});

test("rejects UTC timestamp without timezone", () => {
  const invalid = { ...utc, value: "2026-10-25T12:00:00" } as TemporalValue;
  assert.ok(validateTemporalValue(invalid).some((e) => e.includes("timezone")));
});

test("requires clock identity for logical clocks", () => {
  const invalid: TemporalValue = {
    basis: "logical-clock",
    value: 5,
    source: "test-fixture",
  };
  assert.ok(validateTemporalValue(invalid).some((e) => e.includes("clockId")));
});

test("does not invent a mapping from logical time to UTC", () => {
  const logical: TemporalValue = {
    basis: "logical-clock",
    value: 5,
    clockId: "agent-a",
    epoch: "run-1",
    source: "test-fixture",
  };
  const result = evaluateTemporalTransition(logical, undefined, "t-1");
  assert.equal(result.decision.decision, "defer");
  assert.equal(result.decision.preservesTrustedState, true);
});

test("canonicalizes UTC instant using explicit mapping", () => {
  const result = evaluateTemporalTransition(utc, utcCanonicalization, "t-2");
  assert.equal(result.decision.decision, "accept");
  assert.equal(result.transition?.target.value, "2026-10-25T19:00:00.000Z");
});

test("flags conditional/lossy mappings for limited acceptance", () => {
  const mapping = {
    ...utcCanonicalization,
    id: "lossy-demo",
    reversibility: "lossy" as const,
  };
  const result = evaluateTemporalTransition(utc, mapping, "t-3");
  assert.equal(result.decision.decision, "accept-with-limits");
});

test("rejects mapping that returns wrong target basis", () => {
  const badMapping = {
    ...utcCanonicalization,
    convert: (source: TemporalValue) => ({
      ...source,
      basis: "logical-clock" as const,
      value: 42,
      clockId: "fake",
      epoch: "run",
    }),
  };
  const result = evaluateTemporalTransition(utc, badMapping, "t-4");
  assert.equal(result.decision.decision, "reject-or-isolate");
});


test("temporal conversion catches malformed mapping output without accepting it", () => {
  const badMapping = {
    ...utcCanonicalization,
    id: "bad-output",
    convert: () => ({ basis: "utc-instant", value: "not-a-date", source: "test" }) as TemporalValue,
  };
  const result = evaluateTemporalTransition(utc, badMapping, "t-bad-output");
  assert.equal(result.decision.decision, "reject-or-isolate");
  assert.equal(result.decision.preservesTrustedState, true);
});
