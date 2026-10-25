import { createHash, randomUUID } from "node:crypto";
import type { AdmissionRequest, BoundaryAuditEvent, BoundaryRecord, BoundaryStatus, CaptureBoundaryInput } from "./types.ts";

const POLICY_VERSION = "boundary-admission-v1";
const ALLOWED: Readonly<Record<BoundaryStatus, readonly BoundaryStatus[]>> = {
  captured: ["quarantined", "verified", "rejected"],
  quarantined: ["verified", "rejected"],
  verified: ["admitted", "quarantined", "rejected"],
  admitted: ["quarantined"],
  rejected: [],
};

function canonical(value: unknown): string {
  if (value === null || typeof value !== "object") return JSON.stringify(value) ?? "null";
  if (Array.isArray(value)) return `[${value.map(canonical).join(",")}]`;
  const obj = value as Record<string, unknown>;
  return `{${Object.keys(obj).sort().map(k => `${JSON.stringify(k)}:${canonical(obj[k])}`).join(",")}}`;
}
function sha256(value: string): string { return createHash("sha256").update(value).digest("hex"); }
function requireText(value: string, name: string): void {
  if (!value || !value.trim()) throw new Error(`${name} is required`);
}

/** In-memory reference implementation. Production deployments must persist records and events transactionally in PostgreSQL. */
export class BoundaryService {
  private readonly records = new Map<string, BoundaryRecord>();
  private readonly events: BoundaryAuditEvent[] = [];

  capture<T>(input: CaptureBoundaryInput<T>): BoundaryRecord<T> {
    requireText(input.projectId, "projectId");
    requireText(input.sourceType, "sourceType");
    requireText(input.sourceLocator, "sourceLocator");
    requireText(input.capturedBy, "capturedBy");
    const id = input.id ?? randomUUID();
    if (this.records.has(id)) throw new Error(`Boundary record already exists: ${id}`);
    const now = new Date().toISOString();
    const payloadHash = sha256(canonical(input.payload));
    const ambiguous = (input.ambiguityReasons?.length ?? 0) > 0 || (input.unknownFields?.length ?? 0) > 0 || !input.sourceRevision;
    const status: BoundaryStatus = ambiguous ? "quarantined" : "captured";
    const record: BoundaryRecord<T> = {
      id, projectId: input.projectId, kind: input.kind, payload: structuredClone(input.payload),
      provenance: {
        sourceType: input.sourceType, sourceLocator: input.sourceLocator,
        sourceRevision: input.sourceRevision ? { state: "known", value: input.sourceRevision } : { state: "unknown", reason: "Source revision was not supplied" },
        contentSha256: payloadHash, capturedAt: now, capturedBy: input.capturedBy,
      },
      status, ambiguityReasons: [...(input.ambiguityReasons ?? [])], unknownFields: [...(input.unknownFields ?? [])],
      evidenceIds: [...(input.evidenceIds ?? [])], createdAt: now, updatedAt: now, version: 1,
    };
    this.records.set(id, record);
    this.event(record, input.capturedBy, "capture", null, status, status === "quarantined" ? "Captured with unresolved fields or ambiguity" : "Source captured; not admitted", [], POLICY_VERSION);
    return structuredClone(record);
  }

  get(projectId: string, id: string): BoundaryRecord {
    const record = this.records.get(id);
    if (!record || record.projectId !== projectId) throw new Error("Boundary record not found");
    return structuredClone(record);
  }

  list(projectId: string): BoundaryRecord[] {
    return [...this.records.values()].filter(r => r.projectId === projectId).map(r => structuredClone(r));
  }

  quarantine(projectId: string, id: string, actor: string, reason: string): BoundaryRecord {
    return this.transition(projectId, id, "quarantined", actor, reason, []);
  }

  verify(projectId: string, id: string, actor: string, evidenceIds: readonly string[], expectedRevision: string): BoundaryRecord {
    const current = this.get(projectId, id);
    if (current.provenance.sourceRevision.state !== "known" || current.provenance.sourceRevision.value !== expectedRevision) {
      throw new Error("Source revision is unknown or does not match verification revision");
    }
    if (!evidenceIds.length) throw new Error("Verification requires evidence references");
    if (current.unknownFields.length || current.ambiguityReasons.length) throw new Error("Unresolved unknown fields or ambiguity block verification");
    const next = this.transition(projectId, id, "verified", actor, "Verification recorded against matching source revision", evidenceIds);
    return next;
  }

  admit(projectId: string, id: string, request: AdmissionRequest): BoundaryRecord {
    const current = this.get(projectId, id);
    if (current.status !== "verified") throw new Error("Admission denied: record must be verified first");
    requireText(request.actor, "actor"); requireText(request.reviewer, "reviewer"); requireText(request.reason, "reason"); requireText(request.policyVersion, "policyVersion");
    if (request.actor === request.reviewer) throw new Error("Admission denied: proposer and independent reviewer must differ");
    if (current.provenance.sourceRevision.state !== "known" || current.provenance.sourceRevision.value !== request.expectedSourceRevision) throw new Error("Admission denied: source revision mismatch or unknown");
    if (current.unknownFields.length || current.ambiguityReasons.length) throw new Error("Admission denied: unresolved fields or ambiguity remain");
    if (!request.evidenceIds.length || !request.evidenceIds.every(id => current.evidenceIds.includes(id))) throw new Error("Admission denied: evidence must be attached to the verified record");
    const checks = new Map(request.checks.map(c => [c.name, c]));
    for (const name of request.requiredChecks) {
      const check = checks.get(name);
      if (!check || !check.passed) throw new Error(`Admission denied: required check missing or failed: ${name}`);
    }
    return this.transition(projectId, id, "admitted", request.reviewer, request.reason, request.evidenceIds, request.policyVersion);
  }

  audit(projectId: string): BoundaryAuditEvent[] {
    return this.events.filter(e => e.projectId === projectId).map(e => structuredClone(e));
  }

  private transition(projectId: string, id: string, to: BoundaryStatus, actor: string, reason: string, evidenceIds: readonly string[], policyVersion = POLICY_VERSION): BoundaryRecord {
    requireText(actor, "actor"); requireText(reason, "reason");
    const current = this.get(projectId, id);
    if (!ALLOWED[current.status].includes(to)) throw new Error(`Invalid boundary transition: ${current.status} -> ${to}`);
    const updated: BoundaryRecord = { ...current, status: to, evidenceIds: [...new Set([...current.evidenceIds, ...evidenceIds])], updatedAt: new Date().toISOString(), version: current.version + 1 };
    this.records.set(id, updated);
    this.event(updated, actor, "status-transition", current.status, to, reason, evidenceIds, policyVersion);
    return structuredClone(updated);
  }

  private event(record: BoundaryRecord, actor: string, action: string, fromStatus: BoundaryStatus | null, toStatus: BoundaryStatus, reason: string, evidenceIds: readonly string[], policyVersion: string): void {
    this.events.push({ id: randomUUID(), recordId: record.id, projectId: record.projectId, actor, action, fromStatus, toStatus, reason, policyVersion, evidenceIds: [...evidenceIds], occurredAt: new Date().toISOString() });
  }
}

export function hashBoundaryPayload(payload: unknown): string { return sha256(canonical(payload)); }
