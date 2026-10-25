import { randomUUID } from "node:crypto";
import type { EvidenceItem } from "../cpi/types.ts";

export interface ContractSecurityObservation {
  contractId: string;
  sourceRevision: string;
  functions: Array<{ signature: string; externallyCallable: boolean; authorizationMechanism?: string }>;
  stateTransitions: Array<{ name: string; preconditions: string[]; postconditions: string[] }>;
  evidence: EvidenceItem[];
}

export interface InvariantCandidate {
  id: string;
  contractId: string;
  statement: string;
  rationale: string;
  evidenceIds: string[];
  status: "hypothesis-only";
  requiredValidation: string[];
}

/**
 * A conservative bridge for security analysis. It proposes reviewable invariant candidates
 * from supplied metadata; it does not parse Solidity, execute tests, or declare a finding valid.
 */
export function proposeAuthorizationInvariants(input: ContractSecurityObservation): InvariantCandidate[] {
  const candidates: InvariantCandidate[] = [];
  for (const fn of input.functions.filter(f => f.externallyCallable && !f.authorizationMechanism)) {
    candidates.push({
      id: randomUUID(),
      contractId: input.contractId,
      statement: `Externally callable function ${fn.signature} must enforce its intended authorization policy.`,
      rationale: "The supplied observation lists an externally callable function without an identified authorization mechanism; this is a review prompt, not proof of a vulnerability.",
      evidenceIds: input.evidence.map(e => e.id),
      status: "hypothesis-only",
      requiredValidation: ["Inspect pinned source and inherited modifiers", "Determine whether authorization is required by the specification", "Write positive and negative tests", "Run the approved test suite and preserve execution receipts"],
    });
  }
  return candidates;
}
