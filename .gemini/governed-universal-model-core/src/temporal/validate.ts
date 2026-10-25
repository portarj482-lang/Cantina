import type { TemporalValue } from "./types.ts";

const NUMERIC_BASES = new Set([
  "monotonic-duration",
  "logical-clock",
  "event-time",
  "processing-time",
  "simulation-time",
  "model-version",
  "transaction-time",
]);

export function validateTemporalValue(value: TemporalValue): string[] {
  const errors: string[] = [];

  if (!value.source || !value.source.trim()) errors.push("source is required");

  if (value.basis === "utc-instant") {
    if (typeof value.value !== "string" || Number.isNaN(Date.parse(value.value))) {
      errors.push("utc-instant requires a parseable ISO-8601 timestamp string");
    } else if (!/(Z|[+-]\d{2}:\d{2})$/i.test(value.value)) {
      errors.push("utc-instant must include an explicit timezone offset or Z");
    }
  } else if (NUMERIC_BASES.has(value.basis)) {
    if (typeof value.value !== "number" || !Number.isFinite(value.value)) {
      errors.push(`${value.basis} requires a finite numeric value`);
    }
  }

  if (["monotonic-duration", "logical-clock", "simulation-time", "model-version", "transaction-time"].includes(value.basis) && !value.clockId) {
    errors.push(`${value.basis} requires clockId`);
  }
  if (["logical-clock", "simulation-time", "model-version", "transaction-time"].includes(value.basis) && !value.epoch) {
    errors.push(`${value.basis} requires epoch`);
  }
  if (value.uncertainty && (!Number.isFinite(value.uncertainty.value) || value.uncertainty.value < 0)) {
    errors.push("uncertainty must be a finite non-negative value");
  }
  return errors;
}
