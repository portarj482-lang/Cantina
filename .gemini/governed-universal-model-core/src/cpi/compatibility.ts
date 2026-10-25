import type { CompatibilityReport, Reversibility } from "./types.ts";

export function assessCompatibility(input: {
  sourceModelId: string;
  targetModelId: string;
  sourceInvariantIds: string[];
  targetInvariantIds: string[];
  requiredInvariantIds: string[];
  conflicts?: string[];
  reversibility: Reversibility;
  evidenceIds?: string[];
}): CompatibilityReport {
  const target = new Set(input.targetInvariantIds);
  const preservedInvariants = input.requiredInvariantIds.filter(id => input.sourceInvariantIds.includes(id) && target.has(id));
  const missingInvariants = input.requiredInvariantIds.filter(id => !preservedInvariants.includes(id));
  const conflicts = [...(input.conflicts ?? [])];
  const compatible = conflicts.length > 0 || missingInvariants.length > 0
    ? false
    : input.requiredInvariantIds.length === 0 ? "undetermined" : true;
  const disposition = compatible === false ? "reject" : compatible === "undetermined" || input.reversibility === "unknown" ? "abstain" : "recommend";
  return {
    sourceModelId: input.sourceModelId,
    targetModelId: input.targetModelId,
    compatible,
    preservedInvariants,
    missingInvariants,
    conflicts,
    reversibility: input.reversibility,
    evidenceIds: [...(input.evidenceIds ?? [])],
    disposition,
  };
}
