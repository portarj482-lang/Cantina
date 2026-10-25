import { randomUUID } from "node:crypto";
import type { ModelObservation, SemanticInterpretation } from "./types.ts";

/** Deterministic baseline parser. It does not infer facts that were not supplied. */
export function observeModel(input: {
  subjectId: string;
  source: string;
  facts: ModelObservation["facts"];
  unknowns?: string[];
}): ModelObservation {
  if (!input.subjectId.trim() || !input.source.trim()) throw new Error("subjectId and source are required");
  const keys = new Set<string>();
  for (const fact of input.facts) {
    if (!fact.key.trim()) throw new Error("Every observed fact requires a key");
    if (keys.has(fact.key)) throw new Error(`Duplicate observation key: ${fact.key}`);
    keys.add(fact.key);
  }
  return {
    subjectId: input.subjectId,
    observedAt: new Date().toISOString(),
    source: input.source,
    facts: structuredClone(input.facts),
    unknowns: [...(input.unknowns ?? [])],
  };
}

/** Produces a deliberately conservative interpretation from explicit facts only. */
export function interpretObservation(observation: ModelObservation): SemanticInterpretation {
  const concepts = observation.facts.map(f => f.key);
  const evidenceIds = [...new Set(observation.facts.flatMap(f => f.evidenceId ? [f.evidenceId] : []))];
  return {
    subjectId: observation.subjectId,
    summary: `Observed ${observation.facts.length} explicit fact(s) from ${observation.source}. This summary does not establish facts beyond the supplied observation.`,
    concepts,
    relationships: [],
    assumptions: [],
    unresolvedQuestions: [...observation.unknowns],
    evidenceIds,
  };
}

export function newHypothesis(claim: string, basis: string[], confidence: "low" | "moderate" | "high" = "low") {
  return { id: randomUUID(), claim, confidence, basis: [...basis], counterevidence: [], status: "unverified" as const };
}
