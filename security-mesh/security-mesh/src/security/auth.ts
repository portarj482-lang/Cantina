import { createHash, timingSafeEqual } from 'node:crypto';
import type { FastifyRequest, FastifyReply } from 'fastify';
import { config } from '../config.js';
import { pool } from '../db/pool.js';
import type { Role, AuthenticatedPrincipal } from './roles.js';
export * from './roles.js';

function constantTimeEqual(received: string | undefined, expected: string): boolean {
  if (!received) return false;
  const left = Buffer.from(received);
  const right = Buffer.from(expected);
  return left.length === right.length && timingSafeEqual(left, right);
}

export type CredentialKind = 'api' | 'admin' | 'approval' | 'runner';

export function credentialIsValid(kind: CredentialKind, received: string | undefined): boolean {
  const expected = {
    api: config.API_TOKEN,
    admin: config.ADMIN_API_TOKEN,
    approval: config.HUMAN_APPROVAL_TOKEN,
    runner: config.RUNNER_TOKEN,
  }[kind];
  return constantTimeEqual(received, expected);
}

export function actorId(request: FastifyRequest): string | undefined {
  const value = request.headers['x-actor-id'];
  if (typeof value !== 'string' || !/^[a-zA-Z0-9][a-zA-Z0-9._:@/-]{2,99}$/.test(value)) return undefined;
  return value;
}

export function authHeaderToken(request: FastifyRequest): string | undefined {
  const value = request.headers.authorization;
  if (typeof value !== 'string' || !value.startsWith('Bearer ')) return undefined;
  return value.slice('Bearer '.length);
}

export function runnerIdentifier(request: FastifyRequest): string {
  const value = request.headers['x-runner-id'];
  return config.NODE_ENV === 'production' && typeof value === 'string' ? value : config.RUNNER_ID;
}

export async function registeredRunnerCredential(request: FastifyRequest): Promise<boolean> {
  const runnerId = request.headers['x-runner-id'];
  const token = request.headers['x-runner-token'];
  if (typeof runnerId !== 'string' || typeof token !== 'string') return false;
  const result = await pool.query('SELECT token_sha256 FROM runner_identities WHERE runner_id=$1 AND enabled=true', [runnerId]);
  if (!result.rows[0]) return false;
  const supplied = Buffer.from(createHash('sha256').update(token).digest('hex'));
  const expected = Buffer.from(String(result.rows[0].token_sha256));
  return supplied.length === expected.length && timingSafeEqual(supplied, expected);
}

export async function resolvePrincipal(request: FastifyRequest): Promise<AuthenticatedPrincipal | undefined> {
  const now = new Date().toISOString();
  const rawActor = actorId(request);

  // 1. Administrator token
  const adminHeader = request.headers['x-admin-token'];
  if (typeof adminHeader === 'string' && credentialIsValid('admin', adminHeader)) {
    return {
      id: rawActor ? `admin:${rawActor}` : 'admin:system',
      role: 'administrator',
      actorLabel: rawActor,
      authenticatedAt: now,
    };
  }

  // 2. Approver / Human approval token
  const approvalHeader = request.headers['x-approval-token'];
  if (typeof approvalHeader === 'string' && credentialIsValid('approval', approvalHeader)) {
    return {
      id: rawActor ? `approver:${rawActor}` : 'approver:default',
      role: 'approver',
      actorLabel: rawActor,
      authenticatedAt: now,
    };
  }

  // 3. Runner credentials
  const runnerHeader = request.headers['x-runner-token'];
  if (typeof runnerHeader === 'string') {
    const isRegistered = config.NODE_ENV === 'production' ? await registeredRunnerCredential(request) : credentialIsValid('runner', runnerHeader);
    if (isRegistered) {
      const runnerId = runnerIdentifier(request);
      return {
        id: `runner:${runnerId}`,
        role: 'runner',
        actorLabel: runnerId,
        authenticatedAt: now,
      };
    }
  }

  // 4. API Bearer token
  const bearer = authHeaderToken(request);
  if (typeof bearer === 'string' && credentialIsValid('api', bearer)) {
    const requestedRoleHeader = request.headers['x-requested-role'];
    const role: Role = (requestedRoleHeader === 'reviewer' && rawActor) ? 'reviewer' : 'researcher';
    return {
      id: rawActor ? `${role}:${rawActor}` : `api:${role}`,
      role,
      actorLabel: rawActor,
      authenticatedAt: now,
    };
  }

  return undefined;
}

export async function requirePrincipal(
  request: FastifyRequest,
  reply: FastifyReply,
  requiredRoles?: Role | Role[]
): Promise<AuthenticatedPrincipal | undefined> {
  const principal = await resolvePrincipal(request);
  if (!principal) {
    await reply.code(401).send({ error: 'unauthorized', message: 'Valid authentication credentials required.' });
    return undefined;
  }

  if (requiredRoles) {
    const allowed = Array.isArray(requiredRoles) ? requiredRoles : [requiredRoles];
    if (!allowed.includes(principal.role)) {
      await reply.code(403).send({
        error: 'forbidden',
        message: `Role '${principal.role}' is not authorized. Required: ${allowed.join(', ')}`,
      });
      return undefined;
    }
  }

  return principal;
}

export async function requireApi(request: FastifyRequest, reply: FastifyReply): Promise<boolean> {
  if (credentialIsValid('api', authHeaderToken(request))) return true;
  if (credentialIsValid('runner', request.headers['x-runner-token'] as string | undefined)) return true;
  if (config.NODE_ENV === 'production' && (await registeredRunnerCredential(request))) return true;
  await reply.code(401).send({ error: 'unauthorized', message: 'Valid API bearer token or runner credential required.' });
  return false;
}

export async function requireCredential(request: FastifyRequest, reply: FastifyReply, kind: CredentialKind): Promise<boolean> {
  if (kind === 'runner' && config.NODE_ENV === 'production') {
    if (await registeredRunnerCredential(request)) return true;
    await reply.code(401).send({ error: 'unauthorized', message: 'A registered runner identity is required.' });
    return false;
  }
  const header = kind === 'admin' ? 'x-admin-token' : kind === 'approval' ? 'x-approval-token' : kind === 'runner' ? 'x-runner-token' : undefined;
  const token = header ? request.headers[header] : authHeaderToken(request);
  const received = typeof token === 'string' ? token : undefined;
  if (credentialIsValid(kind, received)) return true;
  await reply.code(401).send({ error: 'unauthorized', message: `Valid ${kind} credential required.` });
  return false;
}

export async function requireActor(request: FastifyRequest, reply: FastifyReply): Promise<string | undefined> {
  const actor = actorId(request);
  if (actor) return actor;
  await reply.code(400).send({ error: 'missing_actor', message: 'x-actor-id is required for audited operations.' });
  return undefined;
}
