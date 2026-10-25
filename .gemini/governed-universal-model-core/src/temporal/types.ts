/**
 * Temporal types for GUMC + CPI.
 *
 * These types distinguish instants, elapsed durations, logical ordering,
 * simulation time, and model-version order. They are not interchangeable.
 */

export type TemporalBasis =
  | "utc-instant"
  | "monotonic-duration"
  | "logical-clock"
  | "event-time"
  | "processing-time"
  | "simulation-time"
  | "model-version"
  | "transaction-time";

export type TimeUnit = "nanoseconds" | "microseconds" | "milliseconds" | "seconds" | "minutes" | "hours" | "ticks";

export interface TemporalValue {
  readonly basis: TemporalBasis;
  /** Canonical ISO-8601 UTC string for utc-instant; finite number for numeric bases. */
  readonly value: string | number;
  readonly unit?: TimeUnit;
  /** Required for monotonic, logical, simulation, and version-scoped values. */
  readonly clockId?: string;
  /** Epoch/version identity for the value's coordinate system. */
  readonly epoch?: string;
  /** Optional bounded uncertainty; meaning must be documented by the producer. */
  readonly uncertainty?: {
    readonly value: number;
    readonly unit: TimeUnit;
    readonly interpretation: "maximum-error" | "standard-deviation" | "unspecified";
  };
  readonly source: string;
}

export type Reversibility = "exact" | "conditional" | "lossy" | "not-applicable";

export interface TemporalTransition {
  readonly id: string;
  readonly source: TemporalValue;
  readonly target: TemporalValue;
  readonly conversionId: string;
  readonly assumptions: readonly string[];
  readonly evidenceIds: readonly string[];
  readonly reversibility: Reversibility;
  readonly status: "proposed" | "verified" | "rejected";
  readonly limitations: readonly string[];
}

export interface TemporalDecision {
  readonly decision: "accept" | "accept-with-limits" | "defer" | "reject-or-isolate";
  readonly reasons: readonly string[];
  readonly preservesTrustedState: true;
}
