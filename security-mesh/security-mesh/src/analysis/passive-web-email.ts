import { resolve4, resolve6, resolveMx, resolveTxt } from 'node:dns/promises';
import { request as httpsRequest } from 'node:https';
import { isIP } from 'node:net';
import type { IncomingHttpHeaders } from 'node:http';

export interface PassiveCheck { host: string; kind: string; status: 'info' | 'warning' | 'error'; detail: string }
const safeHeaders = ['strict-transport-security', 'content-security-policy', 'x-content-type-options', 'referrer-policy', 'permissions-policy'];

function publicAddress(ip: string): boolean {
  if (isIP(ip) === 4) {
    const octets = ip.split('.').map(Number);
    return !(octets[0] === 0 || octets[0] === 10 || octets[0] === 127 || octets[0]! >= 224 ||
      (octets[0] === 169 && octets[1] === 254) || (octets[0] === 172 && octets[1]! >= 16 && octets[1]! <= 31) ||
      (octets[0] === 192 && (octets[1] === 168 || octets[1] === 0 || octets[1] === 2)) ||
      (octets[0] === 198 && (octets[1] === 18 || octets[1] === 19 || octets[1] === 51)) ||
      (octets[0] === 203 && octets[1] === 0 && octets[2] === 113) ||
      (octets[0] === 100 && octets[1]! >= 64 && octets[1]! <= 127));
  }
  const normalized = ip.toLowerCase();
  return (normalized.startsWith('2') || normalized.startsWith('3')) && !normalized.startsWith('2001:db8:');
}

async function publicAddresses(host: string): Promise<string[]> {
  if (isIP(host)) {
    if (!publicAddress(host)) throw new Error('Private or reserved target address is denied.');
    return [host];
  }
  const results = await Promise.allSettled([resolve4(host), resolve6(host)]);
  const addresses = results.flatMap((result) => result.status === 'fulfilled' ? result.value : []);
  if (!addresses.length || addresses.some((address) => !publicAddress(address))) throw new Error('Target DNS did not resolve exclusively to public addresses.');
  return addresses;
}

function head(host: string, ip: string, signal: AbortSignal): Promise<{ status: number; headers: IncomingHttpHeaders }> {
  return new Promise((resolve, reject) => {
    const req = httpsRequest({ hostname: host, servername: isIP(host) ? undefined : host, method: 'HEAD', path: '/', timeout: 4000, signal,
      lookup: (_hostname, _options, callback) => callback(null, ip, isIP(ip)) }, (res) => {
      res.resume(); resolve({ status: res.statusCode ?? 0, headers: res.headers });
    });
    req.on('timeout', () => req.destroy(new Error('HTTPS check timed out.')));
    req.on('error', reject); req.end();
  });
}

/** Passive, bounded checks only: public DNS, HTTPS HEAD at '/', and public mail DNS records. */
export async function assessPublicHost(hostInput: string, signal?: AbortSignal): Promise<PassiveCheck[]> {
  const host = hostInput.toLowerCase().replace(/\.$/, '');
  const checks: PassiveCheck[] = [];
  try {
    const addresses = await publicAddresses(host);
    checks.push({ host, kind: 'dns', status: 'info', detail: `${addresses.length} public address(es) resolved.` });
    const controller = new AbortController();
    const onAbort = () => controller.abort(signal?.reason);
    signal?.addEventListener('abort', onAbort, { once: true });
    try {
      const result = await head(host, addresses[0]!, controller.signal);
      for (const header of safeHeaders) checks.push({ host, kind: `http-header:${header}`, status: result.headers[header] ? 'info' : 'warning', detail: result.headers[header] ? 'Present on HTTPS HEAD response.' : 'Not present on HTTPS HEAD response.' });
      checks.push({ host, kind: 'https', status: result.status >= 200 && result.status < 400 ? 'info' : 'warning', detail: `HTTPS HEAD returned ${result.status}; redirects are not followed.` });
    } finally { signal?.removeEventListener('abort', onAbort); }
  } catch (error) {
    checks.push({ host, kind: 'https', status: 'warning', detail: error instanceof Error ? error.message.slice(0, 300) : 'HTTPS check unavailable.' });
  }
  return checks;
}

export async function assessMailDns(hostInput: string): Promise<PassiveCheck[]> {
  const host = hostInput.toLowerCase().replace(/^\*\./, '').replace(/\.$/, '');
  const checks: PassiveCheck[] = [];
  try {
    const mx = await resolveMx(host);
    checks.push({ host, kind: 'email-mx', status: mx.length ? 'info' : 'warning', detail: mx.length ? `${mx.length} MX record(s) published.` : 'No MX records found.' });
  } catch { checks.push({ host, kind: 'email-mx', status: 'warning', detail: 'MX records unavailable or absent.' }); }
  try {
    const txt = (await resolveTxt(host)).flat().map((x) => x.trim());
    const spf = txt.filter((x) => /^v=spf1\b/i.test(x));
    checks.push({ host, kind: 'email-spf', status: spf.length === 1 ? 'info' : 'warning', detail: spf.length === 1 ? 'One SPF policy published.' : spf.length ? 'Multiple SPF policies published.' : 'No SPF policy found.' });
  } catch { checks.push({ host, kind: 'email-spf', status: 'warning', detail: 'SPF record unavailable or absent.' }); }
  try {
    const txt = (await resolveTxt(`_dmarc.${host}`)).flat();
    const dmarc = txt.find((x) => /^v=DMARC1\b/i.test(x.trim()));
    checks.push({ host, kind: 'email-dmarc', status: dmarc ? 'info' : 'warning', detail: dmarc ? `DMARC policy published (${(dmarc.match(/\bp=([^; ]+)/i)?.[1] ?? 'unspecified').toLowerCase()}).` : 'No DMARC policy found.' });
  } catch { checks.push({ host, kind: 'email-dmarc', status: 'warning', detail: 'DMARC record unavailable or absent.' }); }
  checks.push({ host, kind: 'email-dkim', status: 'info', detail: 'Not tested: DKIM selectors cannot be safely inferred from passive DNS alone.' });
  return checks;
}
