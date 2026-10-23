export type WebTestMethod = 'passive' | 'authenticated-test' | 'rate-limited-active';

export interface WebScope {
  programSlug: string;
  approvedHosts: string[];
  allowedMethods: WebTestMethod[];
  testAccountRequired: boolean;
  maxRequestsPerMinute: number;
  expiresAt: string;
  authorizationRef: string;
}

export interface WebScopeResult { ok: boolean; reason?: string }

function parseHost(value: string): { host: string; wildcard: boolean } | undefined {
  const normalized = value.trim().toLowerCase();
  const wildcard = normalized.startsWith('*.');
  const rawHost = wildcard ? normalized.slice(2) : normalized;
    if (!rawHost || rawHost.includes('*') || rawHost.includes('/') || rawHost.includes(':') || /^\d{1,3}(?:\.\d{1,3}){3}$/.test(rawHost)) return undefined;
    if (wildcard && rawHost.split('.').length < 3) return undefined;
  try {
    const url = new URL(`https://${rawHost}`);
    if (url.hostname !== rawHost || url.username || url.password || url.port) return undefined;
    if (!rawHost.includes('.') || rawHost === 'localhost') return undefined;
    return { host: rawHost, wildcard };
  } catch { return undefined; }
}

export function validateWebScope(scope: WebScope, now = new Date()): WebScopeResult {
  if (!/^[a-z0-9][a-z0-9-]{2,99}$/.test(scope.programSlug)) return { ok: false, reason: 'Invalid program identifier.' };
  if (!scope.approvedHosts.length || scope.approvedHosts.length > 100 || scope.approvedHosts.some((host) => !parseHost(host))) return { ok: false, reason: 'Approved hosts must be explicit DNS names or a single leading wildcard.' };
  if (!scope.allowedMethods.length || scope.allowedMethods.some((method) => !['passive','authenticated-test','rate-limited-active'].includes(method))) return { ok: false, reason: 'At least one supported web test method must be approved.' };
  if (!Number.isInteger(scope.maxRequestsPerMinute) || scope.maxRequestsPerMinute < 1 || scope.maxRequestsPerMinute > 60) return { ok: false, reason: 'Request limit must be between 1 and 60 per minute.' };
  if (!Number.isFinite(Date.parse(scope.expiresAt)) || Date.parse(scope.expiresAt) <= now.getTime()) return { ok: false, reason: 'Web authorization is expired or invalid.' };
  if (!scope.authorizationRef.trim()) return { ok: false, reason: 'Authorization reference is required.' };
  return { ok: true };
}

export function isWebTargetInScope(target: string, approvedHosts: string[]): boolean {
  let parsed: URL;
  try { parsed = new URL(target); } catch { return false; }
  if (parsed.protocol !== 'https:' || parsed.username || parsed.password || parsed.port) return false;
  const host = parsed.hostname.toLowerCase();
  return approvedHosts.some((entry) => {
    const allowed = parseHost(entry);
    if (!allowed) return false;
    return allowed.wildcard ? host !== allowed.host && host.endsWith(`.${allowed.host}`) : host === allowed.host;
  });
}
