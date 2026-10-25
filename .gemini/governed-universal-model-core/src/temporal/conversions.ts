import type { TemporalDecision, TemporalTransition, TemporalValue } from "./types.ts";
import { validateTemporalValue } from "./validate.ts";

export interface TemporalMapping {
  id: string;
  from: TemporalValue["basis"];
  to: TemporalValue["basis"];
  convert: (source: TemporalValue) => TemporalValue;
  assumptions: string[];
  evidenceIds: string[];
  reversibility: TemporalTransition["reversibility"];
  limitations: string[];
}

/**
 * Applies only an explicitly registered mapping. There is deliberately no
 * implicit conversion between wall-clock, logical, monotonic, and simulation time.
 */
export function evaluateTemporalTransition(
  source: TemporalValue,
  mapping: TemporalMapping | undefined,
  transitionId: string,
): { transition?: TemporalTransition; decision: TemporalDecision } {
  const sourceErrors = validateTemporalValue(source);
  if (sourceErrors.length) {
    return {
      decision: {
        decision: "reject-or-isolate",
        reasons: sourceErrors,
        preservesTrustedState: true,
      },
    };
  }

  if (!mapping) {
    return {
      decision: {
        decision: "defer",
        reasons: ["No explicit, reviewed mapping exists for this temporal conversion."],
        preservesTrustedState: true,
      },
    };
  }

  if (mapping.from !== source.basis) {
    return {
      decision: {
        decision: "reject-or-isolate",
        reasons: [`Mapping ${mapping.id} expects ${mapping.from}, received ${source.basis}.`],
        preservesTrustedState: true,
      },
    };
  }

  let target: TemporalValue;
  try {
    target = mapping.convert(source);
  } catch {
    return {
      decision: {
        decision: "reject-or-isolate",
        reasons: ["Mapping failed; source state remains unchanged."],
        preservesTrustedState: true,
      },
    };
  }

  const targetErrors = validateTemporalValue(target);
  if (targetErrors.length || target.basis !== mapping.to) {
    return {
      decision: {
        decision: "reject-or-isolate",
        reasons: [
          ...targetErrors,
          ...(target.basis !== mapping.to ? [`Mapping returned ${target.basis}, expected ${mapping.to}.`] : []),
        ],
        preservesTrustedState: true,
      },
    };
  }

  const transition: TemporalTransition = {
    id: transitionId,
    source,
    target,
    conversionId: mapping.id,
    assumptions: [...mapping.assumptions],
    evidenceIds: [...mapping.evidenceIds],
    reversibility: mapping.reversibility,
    status: mapping.evidenceIds.length > 0 ? "verified" : "proposed",
    limitations: [...mapping.limitations],
  };

  if (transition.status !== "verified") {
    return {
      transition,
      decision: {
        decision: "defer",
        reasons: ["Conversion produced a candidate, but no evidence IDs were supplied to support verification."],
        preservesTrustedState: true,
      },
    };
  }

  if (mapping.reversibility === "lossy" || mapping.reversibility === "conditional") {
    return {
      transition,
      decision: {
        decision: "accept-with-limits",
        reasons: ["Mapping has documented limitations; preserve the source value and lineage."],
        preservesTrustedState: true,
      },
    };
  }

  return {
    transition,
    decision: {
      decision: "accept",
      reasons: ["Explicit mapping produced a valid target and has evidence references."],
      preservesTrustedState: true,
    },
  };
}

/** Safe example: convert a UTC instant to an ISO string representation. */
export const utcCanonicalization: TemporalMapping = {
  id: "utc-canonicalization-v1",
  from: "utc-instant",
  to: "utc-instant",
  convert: (source) => ({
    ...source,
    value: new Date(source.value as string).toISOString(),
  }),
  assumptions: ["Input timestamp includes an explicit timezone offset or Z."],
  evidenceIds: ["test:utc-canonicalization"],
  reversibility: "exact",
  limitations: ["Canonicalization normalizes textual representation; original input should be retained separately if byte-level fidelity matters."],
};

/** Example of a conversion that must not be guessed: logical clock to UTC. */
export const noLogicalToUtcMapping: undefined = undefined;
