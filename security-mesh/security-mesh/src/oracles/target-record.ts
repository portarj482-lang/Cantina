import { createHash } from 'node:crypto';
import type { ScopeRecord } from '../policy/scope.js';
import type { Method, TargetRecordCreateInput } from '../schemas.js';
import { getSuite } from '../tools/registry.js';

export interface TargetRecordBinding extends Omit<TargetRecordCreateInput, 'allowedMethods'> {
  id?: string;
  allowedMethods: Method[];
  programSlug: string;
  scopeSha256: string;
  disabledAt?: string | null;
}
export function scopeFromDatabase(row: Record<string, unknown>): ScopeRecord & { disabledAt?: string | null } {
  return {
    id: String(row.id), programSlug: String(row.program_slug), repositoryUrl: String(row.repository_url),
    sourceCommit: String(row.source_commit), chainId: Number(row.chain_id),
    targetAddresses: (row.target_addresses as string[]).map(String), requiredForkBlock: Number(row.required_fork_block),
    allowedMethods: row.allowed_methods as Method[], programAuthorizationRef: String(row.program_authorization_ref),
    expiresAt: new Date(String(row.expires_at)).toISOString(), restrictions: (row.restrictions as Record<string, unknown>) ?? {},
    disabledAt: row.disabled_at ? new Date(String(row.disabled_at)).toISOString() : null,
  };
}
export function targetRecordFromDatabase(row: Record<string, unknown>): TargetRecordBinding {
  return {
    id: String(row.id), scopeId: String(row.scope_id), targetId: String(row.target_id), targetAddress: String(row.target_address),
    repositoryUrl: String(row.repository_url), sourceCommit: String(row.source_commit), chainId: Number(row.chain_id),
    forkBlock: Number(row.fork_block), environment: String(row.environment),
    allowedMethods: row.allowed_methods as Method[], suiteIds: (row.suite_ids as string[]).map(String),
    expiresAt: new Date(String(row.expires_at)).toISOString(), scopeSha256: String(row.scope_sha256),
    ...(row.harness_sha256 ? { harnessSha256: String(row.harness_sha256) } : {}),
    programSlug: String(row.program_slug), disabledAt: row.status === 'revoked' ? String(row.revoked_at ?? 'revoked') : (row.disabled_at ? String(row.disabled_at) : (row.disabledAt ? String(row.disabledAt) : null)),
  };
}
export interface OracleDecision { oracleId: string; outcome: 'allow' | 'deny'; reasons: string[]; bindingSha256?: string; }

function stable(value: unknown): string {
  if (value === null || typeof value !== 'object') return JSON.stringify(value) ?? 'null';
  if (Array.isArray(value)) return `[${value.map(stable).join(',')}]`;
  const record = value as Record<string, unknown>;
  return `{${Object.keys(record).sort().map((key) => `${JSON.stringify(key)}:${stable(record[key])}`).join(',')}}`;
}

export function scopeBindingSha256(scope: ScopeRecord & { disabledAt?: string | null }): string {
  const binding = {
    id: scope.id, programSlug: scope.programSlug, repositoryUrl: scope.repositoryUrl.replace(/\/+$/, '').replace(/\.git$/i, '').toLowerCase(),
    sourceCommit: scope.sourceCommit.toLowerCase(), chainId: scope.chainId,
    targetAddresses: [...scope.targetAddresses].map((address) => address.toLowerCase()).sort(),
    requiredForkBlock: scope.requiredForkBlock, allowedMethods: [...scope.allowedMethods].sort(),
    programAuthorizationRef: scope.programAuthorizationRef, restrictions: scope.restrictions,
    expiresAt: new Date(scope.expiresAt).toISOString(), disabledAt: scope.disabledAt ?? null,
  };
  return createHash('sha256').update(stable(binding)).digest('hex');
}

/** Deterministic Target Record Oracle; no caller-supplied field can assert its own authorization. */
export function validateTargetRecord(
  record: TargetRecordBinding,
  scope: ScopeRecord & { disabledAt?: string | null },
  now = new Date(),
): OracleDecision {
  const reasons: string[] = [];
  if (record.disabledAt) reasons.push('Target record has been revoked.');
  if (record.scopeId !== scope.id) reasons.push('Target record scope ID does not match the loaded scope.');
  if (scope.disabledAt) reasons.push('Authorized scope is disabled.');
  if (Date.parse(scope.expiresAt) <= now.getTime()) reasons.push('Authorized scope has expired.');
  if (!record.expiresAt || !Number.isFinite(Date.parse(record.expiresAt)) || Date.parse(record.expiresAt) <= now.getTime()) reasons.push('Target record is expired or has an invalid expiry.');
  if (record.expiresAt && Date.parse(record.expiresAt) > Date.parse(scope.expiresAt)) reasons.push('Target record expiry exceeds the authorized scope expiry.');
  if (record.programSlug !== scope.programSlug) reasons.push('Program identifier does not match the authorized scope.');
  if (!record.repositoryUrl || !scope.repositoryUrl || record.repositoryUrl.replace(/\/+$/, '').replace(/\.git$/i, '').toLowerCase() !== scope.repositoryUrl.replace(/\/+$/, '').replace(/\.git$/i, '').toLowerCase()) reasons.push('Repository identity does not match the authorized scope.');
  if (!record.sourceCommit || !scope.sourceCommit || record.sourceCommit.toLowerCase() !== scope.sourceCommit.toLowerCase()) reasons.push('Source commit does not match the authorized pin.');
  if (record.chainId !== scope.chainId) reasons.push('Chain ID does not match the authorized environment.');
  if (record.forkBlock !== scope.requiredForkBlock || record.forkBlock <= 0) reasons.push('Fork block does not match the nonzero authorized pin.');
  if (!record.targetAddress || !Array.isArray(scope.targetAddresses) || !scope.targetAddresses.some((address) => address && address.toLowerCase() === record.targetAddress.toLowerCase())) reasons.push('Target address is outside the authorized scope.');
  if (!Array.isArray(record.allowedMethods) || !Array.isArray(scope.allowedMethods) || record.allowedMethods.length === 0 || record.allowedMethods.some((method) => !scope.allowedMethods.includes(method))) reasons.push('Target record requests a method outside the authorized method set.');
  const suiteIds = Array.isArray(record.suiteIds) ? record.suiteIds : [];
  if (new Set(suiteIds).size !== suiteIds.length) reasons.push('Suite IDs must be unique.');
  for (const suiteId of suiteIds) {
    const suite = getSuite(suiteId);
    if (!suite || !suite.dispatchEnabled) reasons.push(`Suite '${suiteId}' has no enabled safe runner profile.`);
    else if (!record.allowedMethods.includes(suite.requiredMethod) || !scope.allowedMethods.includes(suite.requiredMethod)) reasons.push(`Suite '${suiteId}' requires unauthorized method '${suite.requiredMethod}'.`);
  }
  const currentScopeSha = scopeBindingSha256(scope);
  if (!record.scopeSha256 || record.scopeSha256.toLowerCase() !== currentScopeSha) reasons.push('Stored scope digest is stale or does not bind the current scope record.');
  return { oracleId: 'target-record-oracle', outcome: reasons.length ? 'deny' : 'allow', reasons, bindingSha256: currentScopeSha };
}
