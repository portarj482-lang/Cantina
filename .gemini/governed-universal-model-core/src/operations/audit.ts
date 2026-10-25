import { createHash } from "node:crypto";
import type { AuditRecord } from "./types.ts";

/** Demo-only append-only-in-process audit log. Not durable and not tamper-proof against process/host administrators. */
export class OperationsAuditLog {
  private records: AuditRecord[] = [];
  append(input: Omit<AuditRecord, "sequence" | "timestamp">): AuditRecord {
    if (!input.requestId.trim() || !input.tenantId.trim() || !input.actor.trim() || !input.event.trim()) throw new Error("Audit identity fields are required.");
    const record: AuditRecord = { ...structuredClone(input), sequence: this.records.length + 1, timestamp: new Date().toISOString() };
    this.records.push(record);
    return structuredClone(record);
  }
  listForTenant(tenantId: string): AuditRecord[] { return structuredClone(this.records.filter(r => r.tenantId === tenantId)); }
  /** Hash is a consistency fingerprint only; callers must store it externally to gain independent comparison value. */
  fingerprint(tenantId: string): string {
    const records = this.listForTenant(tenantId);
    return createHash("sha256").update(JSON.stringify(records)).digest("hex");
  }
}
