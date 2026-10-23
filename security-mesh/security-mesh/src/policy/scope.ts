import type { ScopeCreateInput, WorkflowCreateInput } from '../schemas.js';

export interface ScopeRecord extends ScopeCreateInput {
  id: string;
  createdAt?: string;
}

export type ScopeMatch = { ok: true; scopeId: string } | { ok: false; reason: string };

function normalizeUrl(url: string): string {
  return url.replace(/\/+$/, '').replace(/\.git$/i, '').toLowerCase();
}

export function matchWorkflowToScope(input: WorkflowCreateInput, scope: ScopeRecord | undefined, now = new Date()): ScopeMatch {
  if (!scope) return { ok: false, reason: 'No matching authorized scope is registered.' };
  if (scope.programSlug !== input.programSlug) return { ok: false, reason: 'Program identifier does not match the registered scope.' };
  if (normalizeUrl(scope.repositoryUrl) !== normalizeUrl(input.repositoryUrl)) return { ok: false, reason: 'Repository identity does not match the registered scope.' };
  if (scope.sourceCommit.toLowerCase() !== input.sourceCommit.toLowerCase()) return { ok: false, reason: 'Source commit is not the explicitly approved commit.' };
  if (scope.chainId !== input.chainId) return { ok: false, reason: 'Chain ID does not match the registered scope.' };
  if (scope.requiredForkBlock !== input.forkBlock) return { ok: false, reason: 'Fork block does not match the registered pinned block.' };
  if (Date.parse(scope.expiresAt) <= now.getTime()) return { ok: false, reason: 'Registered authorization has expired.' };

  const allowedAddresses = new Set(scope.targetAddresses.map((address: string) => address.toLowerCase()));
  const requestedAddresses = input.targetAddresses.map((address: string) => address.toLowerCase());
  if (requestedAddresses.some((address: string) => !allowedAddresses.has(address))) {
    return { ok: false, reason: 'At least one requested contract address is outside the registered scope.' };
  }
  const allowedMethods = new Set<string>(scope.allowedMethods);
  if (input.requestedMethods.some((method: string) => !allowedMethods.has(method))) {
    return { ok: false, reason: 'At least one requested testing method is not authorized.' };
  }
  return { ok: true, scopeId: scope.id };
}

export function normalizeSourcePath(path: string): boolean {
  if (!path || path.includes('\\') || path.startsWith('/') || path.includes('\0')) return false;
  const segments = path.split('/');
  if (segments.some((segment) => !segment || segment === '.' || segment === '..')) return false;
  if (/^[a-zA-Z]:/.test(path)) return false;
  return true;
}
