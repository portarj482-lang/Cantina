import { randomUUID } from "node:crypto";
import type { AuditEvent, GovernanceDecision, ModelDefinition, TransformationProposal } from "./types.ts";
import { decide, defaultPolicy, type GovernancePolicy } from "./policy.ts";

export class ModelRegistry {
  private readonly models = new Map<string, ModelDefinition>();
  register(model: ModelDefinition): void {
    const key = `${model.id}@${model.version}`;
    if (this.models.has(key)) throw new Error(`Model version already registered: ${key}`);
    if (!model.id || !model.version || !model.adapterId || !model.semantics) throw new Error("Model identity, version, adapter, and semantics are required.");
    this.models.set(key, structuredClone(model));
  }
  get(idAndVersion: string): ModelDefinition | undefined {
    const model = this.models.get(idAndVersion);
    return model ? structuredClone(model) : undefined;
  }
  isApproved(idAndVersion: string): boolean { return this.models.get(idAndVersion)?.approved === true; }
}

export class GovernedModelCore {
  readonly registry = new ModelRegistry();
  private readonly audit: AuditEvent[] = [];
  private readonly policy: GovernancePolicy;
  constructor(policy: GovernancePolicy = defaultPolicy) { this.policy = policy; }

  propose(input: Omit<TransformationProposal, "id" | "requestedAt">): TransformationProposal {
    const proposal: TransformationProposal = { ...structuredClone(input), id: randomUUID(), requestedAt: new Date().toISOString() };
    this.record(input.requestedBy, "transformation.proposed", proposal.id, { source: input.sourceModelId, target: input.targetModelId, riskTier: input.riskTier });
    return proposal;
  }

  evaluate(proposal: TransformationProposal): GovernanceDecision {
    const sourceKnown = this.registry.get(proposal.sourceModelId);
    const targetKnown = this.registry.get(proposal.targetModelId);
    const protectedIds = this.policy.constitutionalInvariantIds;
    const decision = decide(proposal, {
      sourceApproved: sourceKnown?.approved === true,
      targetApproved: targetKnown?.approved === true,
      targetKnown: targetKnown !== undefined,
    }, this.policy, protectedIds);
    this.record("governance-policy", "transformation.evaluated", proposal.id, { decision: decision.decision, reasons: decision.reasons, policyVersion: decision.policyVersion });
    return decision;
  }

  /** Constitutional policy is intentionally immutable through the public runtime API. */
  getPolicyVersion(): string { return this.policy.version; }

  getAuditTrail(): AuditEvent[] { return structuredClone(this.audit); }

  private record(actor: string, action: string, subjectId: string, details: Record<string, unknown>): void {
    this.audit.push({ id: randomUUID(), at: new Date().toISOString(), actor, action, subjectId, details: structuredClone(details) });
  }
}
