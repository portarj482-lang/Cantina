import { createHash, randomUUID } from "node:crypto";

export interface TemporalAuditEntry {
  readonly id: string;
  readonly sequence: number;
  readonly recordedAt: string;
  readonly actor: string;
  readonly action: string;
  readonly subjectId: string;
  readonly details: Readonly<Record<string, unknown>>;
  readonly previousHash: string;
  readonly hash: string;
}

/**
 * In-memory hash-linked audit demonstration. This detects many accidental
 * modifications, but is not durable storage or protection against an attacker
 * who can rewrite the entire chain and its trusted head.
 */
export class HashLinkedTemporalAudit {
  private readonly entries: TemporalAuditEntry[] = [];

  append(input: Omit<TemporalAuditEntry, "id" | "sequence" | "recordedAt" | "previousHash" | "hash">): TemporalAuditEntry {
    const previousHash = this.entries.at(-1)?.hash ?? "GENESIS";
    const payload = {
      id: randomUUID(),
      sequence: this.entries.length + 1,
      recordedAt: new Date().toISOString(),
      actor: input.actor,
      action: input.action,
      subjectId: input.subjectId,
      details: structuredClone(input.details),
      previousHash,
    };
    const hash = createHash("sha256").update(stableStringify(payload)).digest("hex");
    const entry: TemporalAuditEntry = { ...payload, hash };
    this.entries.push(entry);
    return structuredClone(entry);
  }

  list(): TemporalAuditEntry[] {
    return structuredClone(this.entries);
  }

  verify(): { valid: boolean; failedSequence?: number } {
    let previousHash = "GENESIS";
    for (let i = 0; i < this.entries.length; i += 1) {
      const entry = this.entries[i]!;
      const { hash, ...payload } = entry;
      const expected = createHash("sha256").update(stableStringify(payload)).digest("hex");
      if (entry.sequence !== i + 1 || entry.previousHash !== previousHash || hash !== expected) {
        return { valid: false, failedSequence: i + 1 };
      }
      previousHash = hash;
    }
    return { valid: true };
  }
}

function stableStringify(value: unknown): string {
  if (value === undefined) return '"[undefined]"';
  if (typeof value === "number" && !Number.isFinite(value)) {
    throw new Error("Audit details must not contain non-finite numbers");
  }
  if (typeof value === "bigint" || typeof value === "function" || typeof value === "symbol") {
    throw new Error("Audit details must be JSON-compatible values");
  }
  if (value === null || typeof value !== "object") return JSON.stringify(value) ?? '"[undefined]"';
  if (Array.isArray(value)) return `[${value.map(stableStringify).join(",")}]`;
  const record = value as Record<string, unknown>;
  return `{${Object.keys(record).sort().map((key) => `${JSON.stringify(key)}:${stableStringify(record[key])}`).join(",")}}`;
}
