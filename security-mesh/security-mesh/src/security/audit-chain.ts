import { createHash } from 'node:crypto';

export interface AuditChainEntry {
  chain_position: number | string;
  id: string;
  actor_id: string;
  action: string;
  subject_type: string;
  subject_id: string;
  details: unknown;
  request_id: string | null;
  created_at: Date | string;
  previous_hash: string | null;
  record_hash: string;
}

function stable(value: unknown): string {
  if (value === null || typeof value !== 'object') return JSON.stringify(value) ?? 'null';
  if (Array.isArray(value)) return `[${value.map(stable).join(',')}]`;
  const object = value as Record<string, unknown>;
  return `{${Object.keys(object).sort().map((key) => `${JSON.stringify(key)}:${stable(object[key])}`).join(',')}}`;
}

export function auditEntryHash(entry: Omit<AuditChainEntry, 'record_hash'>): string {
  const createdAt = entry.created_at instanceof Date ? entry.created_at.toISOString() : new Date(entry.created_at).toISOString();
  return createHash('sha256').update(stable({
    version: 1,
    chainPosition: Number(entry.chain_position),
    previousHash: entry.previous_hash,
    id: entry.id,
    actorId: entry.actor_id,
    action: entry.action,
    subjectType: entry.subject_type,
    subjectId: entry.subject_id,
    details: entry.details,
    requestId: entry.request_id,
    createdAt,
  })).digest('hex');
}

export function verifyAuditChain(entries: AuditChainEntry[]): { valid: boolean; entriesChecked: number; firstInvalidPosition?: number } {
  let previousHash: string | null = null;
  for (let index = 0; index < entries.length; index++) {
    const entry = entries[index]!;
    const expectedPosition = index + 1;
    if (Number(entry.chain_position) !== expectedPosition || entry.previous_hash !== previousHash || auditEntryHash(entry) !== entry.record_hash) {
      return { valid: false, entriesChecked: index, firstInvalidPosition: Number(entry.chain_position) };
    }
    previousHash = entry.record_hash;
  }
  return { valid: true, entriesChecked: entries.length };
}
