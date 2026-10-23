import Fastify, { type FastifyInstance } from 'fastify';
import { createPublicKey, randomBytes, randomUUID } from 'node:crypto';
import { z } from 'zod';
import { config } from './config.js';
import { AGENT_REGISTRY, TOOL_CAPABILITY_REGISTRY, validateAgentRegistry } from './agents/registry.js';
import { pool } from './db/pool.js';
import { agentTaskCreateSchema, artifactUploadSchema, approvalSubmissionSchema, approveRunSchema, evidenceCreateSchema, evidenceVerifySchema, executionReceiptSchema, gateEvaluationSchema, reviewSchema, scopeCreateSchema, sourceManifestSchema, targetRecordCreateSchema, transitionSchema, webScopeCreateSchema, webTargetCheckSchema, workflowCreateSchema } from './schemas.js';
import { actorId, requireActor, requireApi, requireCredential, runnerIdentifier } from './security/auth.js';
import { getSuite, SUITES } from './tools/registry.js';
import { matchWorkflowToScope, normalizeSourcePath, type ScopeRecord } from './policy/scope.js';
import { validateSourceAttestationEvidence } from './policy/source-attestation.js';
import { putArtifact, sha256, loadArtifactByStorageKey } from './storage/artifacts.js';
import { verifyExecutionReceipt } from './evidence/gate.js';
import type { ExecutionReceipt, GateOutcome, WorkflowStatus } from './types.js';
import { assertTransition } from './workflows/state-machine.js';
import type { PoolClient } from 'pg';
import { enqueueAgentTask } from './orchestration/task-queue.js';
import { isWebTargetInScope, validateWebScope, type WebScope } from './policy/web-scope.js';
import { assessMailDns, assessPublicHost } from './analysis/passive-web-email.js';
import { runWorkerLoop } from './orchestration/worker.js';
import { BUILTIN_HANDLERS } from './orchestration/handlers.js';
import { scoreBenchmark } from './evaluation/benchmark.js';
import { suggestTriage } from './providers/gemini.js';
import { geminiTriageRequestSchema } from './providers/gemini-schemas.js';
import { LAYER_REGISTRY, validateLayerRegistry } from './layers/registry.js';
import { ORACLE_REGISTRY } from './oracles/registry.js';
import { scopeBindingSha256, scopeFromDatabase, targetRecordFromDatabase, validateTargetRecord } from './oracles/target-record.js';
import { authorizeTargetDispatch } from './oracles/dispatch.js';
import { selectVerificationProfile } from './oracles/verification-profile.js';
import { bindEvidenceToTarget, validateIndependentHumanReview, validateSeparateSubmissionApproval } from './oracles/evidence-review.js';
import { auditEntryHash, verifyAuditChain, type AuditChainEntry } from './security/audit-chain.js';

function layerEnabled(layerId: string): boolean { return LAYER_REGISTRY[layerId]?.state === 'active'; }

const idParamsSchema = z.object({ id: z.string().uuid() });
const runParamsSchema = z.object({ id: z.string().uuid(), runId: z.string().uuid() });
const manifestBodySchema = z.object({ manifestBase64: z.string().min(4).max(15_000_000) }).strict();
const gateDecisionSchema = z.object({
  decision: z.enum(['supported', 'rejected', 'inconclusive']),
  rationale: z.string().min(20).max(5000),
  evidenceIds: z.array(z.string().uuid()).min(1).max(100),
}).strict();
const reportDraftSchema = z.object({
  findingId: z.string().min(1).max(100),
  targetRecordId: z.string().uuid().optional(),
  title: z.string().min(5).max(250),
  summary: z.string().min(20).max(5000),
  impact: z.string().min(20).max(5000),
  rootCause: z.string().min(20).max(5000),
  reproduction: z.string().min(20).max(8000),
  limitations: z.string().min(10).max(5000),
  evidenceIds: z.array(z.string().uuid()).min(1).max(100),
}).strict();
const webScopeParamsSchema = z.object({ id: z.string().uuid() });
const runnerRegistrationSchema = z.object({
  runnerId: z.string().min(3).max(128).regex(/^[A-Za-z0-9][A-Za-z0-9._:-]+$/),
  publicKeyPem: z.string().min(80).max(5000),
  allowedSuites: z.array(z.string().min(1).max(100)).min(1).max(20),
}).strict();
const scoutPipelineSchema = z.object({
  sourceCommit: z.string().regex(/^(?:[a-fA-F0-9]{40}|[a-fA-F0-9]{64})$/),
  sources: z.record(z.string(), z.string()).refine((sources) => Object.keys(sources).length <= 1000),
  solcSourceUnits: z.record(z.string(), z.unknown()),
}).strict();
const benchmarkEvaluationSchema = z.object({
  datasetId: z.string().min(1).max(100), datasetVersion: z.string().min(1).max(50),
  cases: z.array(z.object({ id: z.string().min(1).max(100), expectedFinding: z.boolean(), detectedFinding: z.boolean(),
    pocExpected: z.boolean().optional(), pocReproduced: z.boolean().optional(), durationMs: z.number().nonnegative().optional(), costUsd: z.number().nonnegative().optional() }).strict()).min(1).max(10000),
}).strict();

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : 'Unknown error';
}

function normalizeRepo(url: string): string {
  return url.replace(/\/+$/, '').replace(/\.git$/i, '').toLowerCase();
}

async function audit(client: PoolClient, actor: string, action: string, subjectType: string, subjectId: string, details: unknown, requestId?: string): Promise<void> {
  await client.query('SELECT pg_advisory_xact_lock($1,$2)', [774411, 1]);
  const latest = await client.query('SELECT chain_position,record_hash FROM execution_audit ORDER BY chain_position DESC LIMIT 1');
  const chainPosition = Number(latest.rows[0]?.chain_position ?? 0) + 1;
  const previousHash = latest.rows[0]?.record_hash ? String(latest.rows[0].record_hash) : null;
  const id = randomUUID();
  const createdAt = new Date();
  const normalizedDetails = JSON.parse(JSON.stringify(details ?? {})) as unknown;
  const entry = {
    chain_position: chainPosition,
    id,
    actor_id: actor,
    action,
    subject_type: subjectType,
    subject_id: subjectId,
    details: normalizedDetails,
    request_id: requestId ?? null,
    created_at: createdAt,
    previous_hash: previousHash,
  };
  const recordHash = auditEntryHash(entry);
  await client.query(
    `INSERT INTO execution_audit (chain_position,previous_hash,record_hash,id,actor_id,action,subject_type,subject_id,details,request_id,created_at)
     VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9::jsonb,$10,$11)`,
    [chainPosition, previousHash, recordHash, id, actor, action, subjectType, subjectId, JSON.stringify(normalizedDetails), requestId ?? null, createdAt],
  );
}

async function auditGemini(actor: string, action: string, details: unknown, requestId: string): Promise<void> {
  const client = await pool.connect();
  try {
    await client.query('BEGIN');
    await audit(client, actor, action, 'gemini_triage_request', requestId, details, requestId);
    await client.query('COMMIT');
  } catch (error) {
    await client.query('ROLLBACK');
    throw error;
  } finally {
    client.release();
  }
}

async function writeGate(client: PoolClient, workflowId: string, gateId: string, outcome: GateOutcome, reasons: string[], actor: string, evidenceIds: string[] = []): Promise<void> {
  await client.query(
    `INSERT INTO readiness_gate_results (id, workflow_id, gate_id, outcome, reasons, evidence_ids, evaluated_by)
     VALUES ($1,$2,$3,$4,$5::jsonb,$6::uuid[],$7)
     ON CONFLICT (workflow_id, gate_id) DO UPDATE SET outcome=EXCLUDED.outcome, reasons=EXCLUDED.reasons, evidence_ids=EXCLUDED.evidence_ids, evaluated_by=EXCLUDED.evaluated_by, evaluated_at=now()`,
    [randomUUID(), workflowId, gateId, outcome, JSON.stringify(reasons), evidenceIds, actor],
  );
}

function mapScopeRow(row: Record<string, unknown>): ScopeRecord {
  return {
    id: String(row.id),
    programSlug: String(row.program_slug),
    repositoryUrl: String(row.repository_url),
    sourceCommit: String(row.source_commit),
    chainId: Number(row.chain_id),
    targetAddresses: (row.target_addresses as string[]).map((x) => String(x)),
    requiredForkBlock: Number(row.required_fork_block),
    allowedMethods: row.allowed_methods as ScopeRecord['allowedMethods'],
    programAuthorizationRef: String(row.program_authorization_ref),
    expiresAt: new Date(String(row.expires_at)).toISOString(),
    restrictions: (row.restrictions as Record<string, unknown>) ?? {},
  };
}

async function bootstrapRegistry(): Promise<void> {
  const client = await pool.connect();
  try {
    await client.query('BEGIN');
    for (const agent of AGENT_REGISTRY) {
      await client.query(
        `INSERT INTO agent_profiles (id, agent_id, version, profile, enabled)
         VALUES ($1,$2,$3,$4::jsonb,$5)
         ON CONFLICT (agent_id) DO UPDATE SET version=EXCLUDED.version, profile=EXCLUDED.profile, enabled=EXCLUDED.enabled`,
        [randomUUID(), agent.id, '1.0.0', JSON.stringify(agent), agent.enabledForEvm],
      );
    }
    for (const suite of Object.values(SUITES)) {
      await client.query(
        `INSERT INTO tool_registry (tool_id, version, definition, enabled) VALUES ($1,$2,$3::jsonb,true)
         ON CONFLICT (tool_id) DO UPDATE SET version=EXCLUDED.version, definition=EXCLUDED.definition, enabled=true`,
        [suite.id, '1.0.0', JSON.stringify(suite)],
      );
    }
    for (const capability of TOOL_CAPABILITY_REGISTRY) {
      await client.query(
        `INSERT INTO tool_registry (tool_id, version, definition, enabled) VALUES ($1,$2,$3::jsonb,false)
         ON CONFLICT (tool_id) DO UPDATE SET version=EXCLUDED.version, definition=EXCLUDED.definition, enabled=false`,
        [capability.toolId, '1.0.0', JSON.stringify(capability)],
      );
    }
    await client.query('COMMIT');
  } catch (error) {
    await client.query('ROLLBACK');
    throw error;
  } finally {
    client.release();
  }
}

export async function createServer(): Promise<FastifyInstance> {
  const app = Fastify({
    logger: { level: config.NODE_ENV === 'production' ? 'info' : 'debug', redact: ['req.headers.authorization', 'req.headers.x-admin-token', 'req.headers.x-approval-token', 'req.headers.x-runner-token'] },
    bodyLimit: 20_500_000,
    genReqId: () => randomUUID(),
  });

  app.setErrorHandler((error, request, reply) => {
    request.log.error({ err: error, requestId: request.id }, 'request failed');
    if (error instanceof z.ZodError) return reply.code(400).send({ error: 'invalid_request', issues: error.issues });
    return reply.code(500).send({ error: 'internal_error', requestId: request.id });
  });

  app.get('/health', async (_request, reply) => {
    try {
      await pool.query('SELECT 1');
      return { ok: true, service: 'antigravity-security-mesh', database: 'reachable', agentCount: AGENT_REGISTRY.length };
    } catch {
      return reply.code(503).send({ ok: false, service: 'antigravity-security-mesh', database: 'unavailable' });
    }
  });

  app.get('/healthz', async () => {
    return { status: 'pass', time: new Date().toISOString() };
  });

  app.get('/readyz', async (_request, reply) => {
    try {
      await pool.query('SELECT 1');
      let migrationCount = 0;
      try {
        const migrations = await pool.query('SELECT count(*)::int AS count FROM _migrations');
        migrationCount = migrations.rows[0]?.count ?? 0;
      } catch {
        // _migrations table may not exist yet if unmigrated
      }
      return {
        status: 'pass',
        service: 'antigravity-security-mesh',
        database: 'connected',
        migrationsApplied: migrationCount,
        time: new Date().toISOString(),
      };
    } catch {
      return reply.code(503).send({ status: 'fail', service: 'antigravity-security-mesh', database: 'unavailable' });
    }
  });

  app.post('/v1/runners/register', async (request, reply) => {
    if (!(await requireCredential(request, reply, 'admin'))) return;
    const actor = await requireActor(request, reply);
    if (!actor) return;
    const parsed = runnerRegistrationSchema.safeParse(request.body);
    if (!parsed.success) return reply.code(400).send({ error: 'invalid_runner_registration', issues: parsed.error.issues });
    if (parsed.data.allowedSuites.some((suiteId) => !['build','baseline-tests','slither'].includes(suiteId) || !getSuite(suiteId))) return reply.code(400).send({ error: 'runner_suite_not_implemented' });
    let publicKey: ReturnType<typeof createPublicKey>;
    try { publicKey = createPublicKey(parsed.data.publicKeyPem); }
    catch { return reply.code(400).send({ error: 'invalid_runner_public_key' }); }
    if (publicKey.asymmetricKeyType !== 'ed25519') return reply.code(400).send({ error: 'runner_key_must_be_ed25519' });
    const oneTimeToken = randomBytes(32).toString('base64url');
    const client = await pool.connect();
    try {
      await client.query('BEGIN');
      await client.query(`INSERT INTO runner_identities (runner_id,token_sha256,public_key_pem,allowed_suites,created_by)
        VALUES ($1,$2,$3,$4,$5) ON CONFLICT (runner_id) DO UPDATE SET token_sha256=EXCLUDED.token_sha256,
        public_key_pem=EXCLUDED.public_key_pem,allowed_suites=EXCLUDED.allowed_suites,enabled=true,rotated_at=now()`,
        [parsed.data.runnerId, sha256(Buffer.from(oneTimeToken)), parsed.data.publicKeyPem, parsed.data.allowedSuites, actor]);
      await audit(client, actor, 'runner.registered_or_rotated', 'runner', parsed.data.runnerId, { allowedSuites: parsed.data.allowedSuites }, request.id);
      await client.query('COMMIT');
    } catch (error) { await client.query('ROLLBACK'); throw error; }
    finally { client.release(); }
    return reply.code(201).send({ runnerId: parsed.data.runnerId, token: oneTimeToken, allowedSuites: parsed.data.allowedSuites, tokenReturnedOnce: true });
  });

  app.post('/v1/runners/:id/revoke', async (request, reply) => {
    if (!(await requireCredential(request, reply, 'admin'))) return;
    const actor = await requireActor(request, reply);
    if (!actor) return;
    const params = z.object({ id: z.string().min(3).max(128) }).safeParse(request.params);
    if (!params.success) return reply.code(400).send({ error: 'invalid_runner_id' });
    const client = await pool.connect();
    try {
      await client.query('BEGIN');
      const revoked = await client.query('UPDATE runner_identities SET enabled=false WHERE runner_id=$1 RETURNING runner_id', [params.data.id]);
      if (!revoked.rows[0]) { await client.query('ROLLBACK'); return reply.code(404).send({ error: 'runner_not_found' }); }
      await client.query(`WITH revoked_runs AS (UPDATE execution_runs SET status='failed',lease_token=NULL,lease_expires_at=NULL
        WHERE runner_id=$1 AND status='running' RETURNING workflow_id)
        UPDATE workflows SET execution_status='failed',updated_at=now() WHERE id IN (SELECT workflow_id FROM revoked_runs)`, [params.data.id]);
      await audit(client, actor, 'runner.revoked', 'runner', params.data.id, {}, request.id);
      await client.query('COMMIT');
      return { runnerId: params.data.id, enabled: false };
    } catch (error) { await client.query('ROLLBACK'); throw error; }
    finally { client.release(); }
  });

  app.post('/v1/runner/claim', async (request, reply) => {
    if (!(await requireCredential(request, reply, 'runner'))) return;
    const runnerId = runnerIdentifier(request);
    const client = await pool.connect();
    try {
      await client.query('BEGIN');
      const claimToken = randomUUID();
      const result = await client.query(
        `WITH candidate AS (
          SELECT r.id,r.workflow_id FROM execution_runs r
          JOIN workflows w ON w.id=r.workflow_id AND w.status='execution' AND w.approval_status='approved'
          JOIN authorized_scopes s ON s.id=w.scope_id AND s.disabled_at IS NULL AND s.expires_at > now()
          JOIN target_records t ON t.id=w.target_record_id AND t.id=r.target_record_id AND t.status='active' AND t.expires_at > now() AND r.suite_id=ANY(t.suite_ids)
          JOIN runner_identities i ON i.runner_id=$1 AND i.enabled=true AND r.suite_id=ANY(i.allowed_suites)
          WHERE (r.status='queued' OR (r.status='running' AND r.lease_expires_at <= now()))
            AND lower(r.source_commit)=lower(s.source_commit) AND r.chain_id=s.chain_id AND r.fork_block=s.required_fork_block
            AND w.target_addresses <@ s.target_addresses
            AND s.allowed_methods @> ARRAY[(SELECT definition->>'requiredMethod' FROM tool_registry WHERE tool_id=r.suite_id)]::text[]
          ORDER BY r.created_at,r.id LIMIT 1 FOR UPDATE OF r SKIP LOCKED
        )
        UPDATE execution_runs r SET status='running',runner_id=$1,lease_token=$2,
          lease_expires_at=now()+interval '20 minutes',started_at=COALESCE(r.started_at,now())
        FROM candidate c WHERE r.id=c.id
        RETURNING r.id,r.workflow_id,r.target_record_id,r.runner_id,r.suite_id,r.command_profile_id,r.repository_url,r.source_commit,r.chain_id,r.fork_block,r.lease_token,r.lease_expires_at`,
        [runnerId, claimToken],
      );
      if (!result.rows[0]) { await client.query('COMMIT'); return { run: null }; }
      const run = result.rows[0];
      const wf = await client.query('SELECT id,approval_status,source_commit,repository_url,chain_id,fork_block,target_addresses,scope_id,target_record_id FROM workflows WHERE id=$1', [run.workflow_id]);
      const scope = await client.query('SELECT * FROM authorized_scopes WHERE id=$1', [wf.rows[0]?.scope_id]);
      const target = await client.query('SELECT t.*,s.program_slug FROM target_records t JOIN authorized_scopes s ON s.id=t.scope_id WHERE t.id=$1 AND t.scope_id=$2', [run.target_record_id, wf.rows[0]?.scope_id]);
      const oracle = wf.rows[0] && scope.rows[0] && target.rows[0]
        ? validateTargetRecord(targetRecordFromDatabase(target.rows[0] as Record<string, unknown>), scopeFromDatabase(scope.rows[0] as Record<string, unknown>))
        : { outcome: 'deny' as const, oracleId: 'target-record-oracle', reasons: ['Missing target-record binding.'] };
      if (!wf.rows[0] || !scope.rows[0] || oracle.outcome !== 'allow' || String(run.target_record_id) !== String(wf.rows[0]?.target_record_id) || String(run.source_commit).toLowerCase() !== String(scope.rows[0].source_commit).toLowerCase() || normalizeRepo(String(run.repository_url)) !== normalizeRepo(String(scope.rows[0].repository_url)) || Number(run.chain_id) !== Number(scope.rows[0].chain_id) || Number(run.fork_block) !== Number(scope.rows[0].required_fork_block)) {
        await client.query("UPDATE execution_runs SET status='failed',lease_token=NULL,lease_expires_at=NULL WHERE id=$1", [run.id]);
        await client.query("UPDATE workflows SET execution_status='failed',updated_at=now() WHERE id=$1", [run.workflow_id]);
        await client.query('COMMIT');
        return reply.code(409).send({ error: 'queued_run_scope_binding_mismatch', oracle });
      }
      await client.query("UPDATE workflows SET execution_status='running',updated_at=now() WHERE id=$1", [run.workflow_id]);
      await audit(client, `runner:${runnerId}`, 'run.claimed', 'execution_run', String(run.id), { runnerId, targetRecordId: run.target_record_id, leaseExpiresAt: run.lease_expires_at }, request.id);
      await client.query('COMMIT');
      return { run: { ...run, workflowId: run.workflow_id }, workflow: wf.rows[0], scope: scope.rows[0], targetRecord: target.rows[0] };
    } catch (error) { await client.query('ROLLBACK'); throw error; }
    finally { client.release(); }
  });

  app.post('/v1/runner/renew', async (request, reply) => {
    if (!(await requireCredential(request, reply, 'runner'))) return;
    const body = z.object({ runId: z.string().uuid(), leaseToken: z.string().uuid() }).strict().safeParse(request.body);
    if (!body.success) return reply.code(400).send({ error: 'invalid_runner_lease' });
    const renewed = await pool.query(`UPDATE execution_runs SET lease_expires_at=now()+interval '20 minutes'
      WHERE id=$1 AND runner_id=$2 AND lease_token=$3 AND status='running' AND lease_expires_at > now() RETURNING lease_expires_at`,
      [body.data.runId, runnerIdentifier(request), body.data.leaseToken]);
    if (!renewed.rows[0]) return reply.code(409).send({ error: 'runner_lease_lost' });
    return { renewed: true, leaseExpiresAt: renewed.rows[0].lease_expires_at };
  });

  app.post('/v1/triage/gemini', { bodyLimit: 25_000 }, async (request, reply) => {
    if (!(await requireCredential(request, reply, 'approval'))) return;
    const actor = await requireActor(request, reply);
    if (!actor) return;
    const parsed = geminiTriageRequestSchema.safeParse(request.body);
    if (!parsed.success) return reply.code(400).send({ error: 'invalid_gemini_triage_request', issues: parsed.error.issues });
    if (!config.GEMINI_TRIAGE_ENABLED || !config.GEMINI_API_KEY) {
      return reply.code(503).send({ error: 'gemini_triage_disabled', enabled: config.GEMINI_TRIAGE_ENABLED, apiKeyConfigured: Boolean(config.GEMINI_API_KEY) });
    }

    const input = {
      findingTitle: parsed.data.findingTitle,
      hypothesis: parsed.data.hypothesis,
      sourceExcerpt: parsed.data.sourceExcerpt,
      observedEvidence: parsed.data.observedEvidence,
    };
    const serializedInput = JSON.stringify(input);
    const payloadSha256 = sha256(Buffer.from(serializedInput, 'utf8'));
    const payloadBytes = Buffer.byteLength(serializedInput, 'utf8');
    const auditBase = { payloadSha256, payloadBytes, evidenceCount: input.observedEvidence.length, model: config.GEMINI_MODEL };
    try {
      await auditGemini(actor, 'gemini.triage.requested', auditBase, request.id);
    } catch {
      request.log.error({ requestId: request.id }, 'Gemini triage blocked because request audit could not be recorded');
      return reply.code(503).send({ error: 'gemini_triage_audit_unavailable' });
    }

    let result: Awaited<ReturnType<typeof suggestTriage>>;
    try {
      result = await suggestTriage(input);
    } catch {
      try {
        await auditGemini(actor, 'gemini.triage.failed', { ...auditBase, outcome: 'provider_error' }, request.id);
      } catch {
        request.log.error({ requestId: request.id }, 'Gemini triage failure audit could not be recorded');
      }
      return reply.code(502).send({ error: 'gemini_triage_provider_failed', requestId: request.id });
    }

    const serializedSuggestion = JSON.stringify(result.suggestion);
    try {
      await auditGemini(actor, 'gemini.triage.completed', {
        ...auditBase,
        outcome: 'advisory',
        responseSha256: sha256(Buffer.from(serializedSuggestion, 'utf8')),
        responseBytes: Buffer.byteLength(serializedSuggestion, 'utf8'),
      }, request.id);
    } catch {
      request.log.error({ requestId: request.id }, 'Gemini triage result audit could not be recorded');
      return reply.code(503).send({ error: 'gemini_triage_result_audit_unavailable', requestId: request.id });
    }

    return {
      status: 'advisory',
      reviewRequired: true,
      provider: 'google-gemini',
      model: result.model,
      inputSha256: payloadSha256,
      suggestion: result.suggestion,
    };
  });

  app.get('/v1/agents', async (request, reply) => {
    if (!(await requireApi(request, reply))) return;
    const issues = validateAgentRegistry();
    return { count: AGENT_REGISTRY.length, registryIssues: issues, agents: AGENT_REGISTRY };
  });

  app.get('/v1/layers', async (request, reply) => {
    if (!(await requireApi(request, reply))) return;
    return { count: Object.keys(LAYER_REGISTRY).length, registryIssues: validateLayerRegistry(), layers: Object.values(LAYER_REGISTRY) };
  });

  app.get('/v1/oracles', async (request, reply) => {
    if (!(await requireApi(request, reply))) return;
    return { count: ORACLE_REGISTRY.length, oracles: ORACLE_REGISTRY };
  });

  app.get('/v1/audit/verify', async (request, reply) => {
    if (!(await requireApi(request, reply))) return;
    const rows = await pool.query('SELECT chain_position,id,actor_id,action,subject_type,subject_id,details,request_id,created_at,previous_hash,record_hash FROM execution_audit ORDER BY chain_position LIMIT 1000001');
    if (rows.rows.length > 1_000_000) return reply.code(413).send({ error: 'audit_chain_limit_exceeded', maxEntries: 1_000_000 });
    const result = verifyAuditChain(rows.rows as AuditChainEntry[]);
    return { ...result, trustNote: 'Verifies database rows against their hash chain; an independent externally retained chain head is required to detect full-database rollback or privileged rewrite.' };
  });

  app.get('/v1/audit/export', async (request, reply) => {
    if (!(await requireApi(request, reply))) return;
    const rows = await pool.query(
      'SELECT chain_position,id,actor_id,action,subject_type,subject_id,details,request_id,created_at,previous_hash,record_hash FROM execution_audit ORDER BY chain_position ASC'
    );
    const verification = verifyAuditChain(rows.rows as AuditChainEntry[]);
    if (!verification.valid) {
      return reply.code(500).send({ error: 'audit_chain_corrupted', firstInvalidPosition: verification.firstInvalidPosition });
    }
    const head = rows.rows.length > 0 ? (rows.rows[rows.rows.length - 1] as AuditChainEntry) : null;
    return {
      exportedAt: new Date().toISOString(),
      entryCount: rows.rows.length,
      chainHeadPosition: head?.chain_position ?? 0,
      chainHeadRecordHash: head?.record_hash ?? null,
      verification,
      entries: rows.rows,
    };
  });

  app.get('/v1/tool-registry', async (request, reply) => {
    if (!(await requireApi(request, reply))) return;
    return { count: Object.keys(SUITES).length + TOOL_CAPABILITY_REGISTRY.length, suiteCount: Object.keys(SUITES).length, capabilityCount: TOOL_CAPABILITY_REGISTRY.length, dispatchEnabled: Object.values(SUITES).some((suite) => suite.dispatchEnabled), suites: Object.values(SUITES), capabilities: TOOL_CAPABILITY_REGISTRY };
  });

  app.get('/v1/scopes', async (request, reply) => {
    if (!(await requireApi(request, reply))) return;
    const result = await pool.query(
      `SELECT id, program_slug, repository_url, source_commit, chain_id, target_addresses, required_fork_block,
              allowed_methods, program_authorization_ref, restrictions, expires_at, created_by, created_at, disabled_at
       FROM authorized_scopes ORDER BY created_at DESC LIMIT 500`,
    );
    return { count: result.rowCount ?? 0, scopes: result.rows };
  });

  app.get('/v1/web-scopes', async (request, reply) => {
    if (!(await requireApi(request, reply))) return;
    const result = await pool.query(
      `SELECT id, program_slug, approved_hosts, allowed_methods, test_account_required, max_requests_per_minute,
              authorization_ref, expires_at, created_by, created_at, disabled_at
       FROM web_scopes ORDER BY created_at DESC LIMIT 500`,
    );
    return { count: result.rowCount ?? 0, scopes: result.rows };
  });

  app.get('/v1/benchmarks', async (request, reply) => {
    if (!(await requireApi(request, reply))) return;
    const result = await pool.query('SELECT id,dataset_id,dataset_version,score,created_by,created_at FROM benchmark_evaluations ORDER BY created_at DESC LIMIT 200');
    return { evaluations: result.rows };
  });

  app.post('/v1/benchmarks/evaluate', async (request, reply) => {
    if (!(await requireApi(request, reply))) return;
    const actor = await requireActor(request, reply);
    if (!actor) return;
    const parsed = benchmarkEvaluationSchema.safeParse(request.body);
    if (!parsed.success) return reply.code(400).send({ error: 'invalid_benchmark_dataset', issues: parsed.error.issues });
    let score;
    try { score = scoreBenchmark(parsed.data.cases.map((item) => ({ id: item.id, expectedFinding: item.expectedFinding, detectedFinding: item.detectedFinding,
      ...(item.pocExpected === undefined ? {} : { pocExpected: item.pocExpected }), ...(item.pocReproduced === undefined ? {} : { pocReproduced: item.pocReproduced }),
      ...(item.durationMs === undefined ? {} : { durationMs: item.durationMs }), ...(item.costUsd === undefined ? {} : { costUsd: item.costUsd }) }))); }
    catch (error) { return reply.code(400).send({ error: 'invalid_benchmark_cases', message: error instanceof Error ? error.message : 'Invalid case labels.' }); }
    const id = randomUUID();
    const client = await pool.connect();
    try {
      await client.query('BEGIN');
      await client.query('INSERT INTO benchmark_evaluations (id,dataset_id,dataset_version,score,case_results,created_by) VALUES ($1,$2,$3,$4::jsonb,$5::jsonb,$6)',
        [id, parsed.data.datasetId, parsed.data.datasetVersion, JSON.stringify(score), JSON.stringify(parsed.data.cases), actor]);
      await audit(client, actor, 'benchmark.evaluated', 'benchmark_evaluation', id, { datasetId: parsed.data.datasetId, datasetVersion: parsed.data.datasetVersion, cases: score.cases }, request.id);
      await client.query('COMMIT');
    } catch (error) { await client.query('ROLLBACK'); throw error; }
    finally { client.release(); }
    return reply.code(201).send({ id, datasetId: parsed.data.datasetId, datasetVersion: parsed.data.datasetVersion, score, caveat: 'Metrics reflect the supplied labels and predictions; they are not an independently validated benchmark.' });
  });

  app.post('/v1/web-scopes', async (request, reply) => {
    if (!(await requireCredential(request, reply, 'admin'))) return;
    const actor = await requireActor(request, reply);
    if (!actor) return;
    const parsed = webScopeCreateSchema.safeParse(request.body);
    if (!parsed.success) return reply.code(400).send({ error: 'invalid_web_scope', issues: parsed.error.issues });
    const scope: WebScope = { ...parsed.data, maxRequestsPerMinute: parsed.data.maxRequestsPerMinute };
    const validation = validateWebScope(scope);
    if (!validation.ok) return reply.code(400).send({ error: 'invalid_web_scope', message: validation.reason });
    const id = randomUUID();
    const client = await pool.connect();
    try {
      await client.query('BEGIN');
      await client.query(
        `INSERT INTO web_scopes (id,program_slug,approved_hosts,allowed_methods,test_account_required,max_requests_per_minute,authorization_ref,expires_at,created_by)
         VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)`,
        [id, scope.programSlug, scope.approvedHosts.map((host) => host.toLowerCase()), scope.allowedMethods, scope.testAccountRequired, scope.maxRequestsPerMinute, scope.authorizationRef, scope.expiresAt, actor],
      );
      await audit(client, actor, 'web_scope.registered', 'web_scope', id, { programSlug: scope.programSlug, hostCount: scope.approvedHosts.length, methods: scope.allowedMethods }, request.id);
      await client.query('COMMIT');
    } catch (error) { await client.query('ROLLBACK'); throw error; }
    finally { client.release(); }
    return reply.code(201).send({ id, status: 'registered', note: 'Authorization metadata is recorded; target checks do not send network requests.' });
  });

  app.post('/v1/web-scopes/:id/check-target', async (request, reply) => {
    if (!(await requireApi(request, reply))) return;
    const params = webScopeParamsSchema.safeParse(request.params);
    const body = webTargetCheckSchema.safeParse(request.body);
    if (!params.success || !body.success) return reply.code(400).send({ error: 'invalid_web_target_check' });
    const result = await pool.query('SELECT * FROM web_scopes WHERE id=$1 AND disabled_at IS NULL', [params.data.id]);
    const row = result.rows[0];
    if (!row || new Date(String(row.expires_at)).getTime() <= Date.now()) return reply.code(404).send({ error: 'active_web_scope_not_found' });
    const inScope = isWebTargetInScope(body.data.target, row.approved_hosts as string[]);
    const methodAllowed = (row.allowed_methods as string[]).includes(body.data.method);
    return { inScope, methodAllowed, authorized: inScope && methodAllowed, target: body.data.target, method: body.data.method, sendsNetworkRequest: false };
  });

  app.post('/v1/web-scopes/:id/assess/web', async (request, reply) => {
    if (!(await requireApi(request, reply))) return;
    const actor = await requireActor(request, reply);
    if (!actor) return;
    const params = webScopeParamsSchema.safeParse(request.params);
    const body = webTargetCheckSchema.safeParse(request.body);
    if (!params.success || !body.success || body.data.method !== 'passive') return reply.code(400).send({ error: 'passive_https_target_required' });
    let target: URL;
    try { target = new URL(body.data.target); } catch { return reply.code(400).send({ error: 'invalid_target' }); }
    if (target.protocol !== 'https:' || target.username || target.password || target.search || target.hash || target.port && target.port !== '443' || target.pathname !== '/') {
      return reply.code(400).send({ error: 'only_https_origin_checks_are_supported' });
    }
    const scopeResult = await pool.query('SELECT * FROM web_scopes WHERE id=$1 AND disabled_at IS NULL', [params.data.id]);
    const scope = scopeResult.rows[0];
    if (!scope || new Date(String(scope.expires_at)).getTime() <= Date.now()) return reply.code(404).send({ error: 'active_web_scope_not_found' });
    if (!(scope.allowed_methods as string[]).includes('passive') || !isWebTargetInScope(target.toString(), scope.approved_hosts as string[])) return reply.code(403).send({ error: 'passive_target_not_authorized' });
    const recent = await pool.query("SELECT count(*)::integer AS n FROM web_assessments WHERE web_scope_id=$1 AND created_at > now() - interval '1 minute'", [params.data.id]);
    if (Number(recent.rows[0]?.n ?? 0) >= Number(scope.max_requests_per_minute)) return reply.code(429).send({ error: 'web_scope_rate_limit_reached' });
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 5000);
    let results;
    try { results = await assessPublicHost(target.hostname, controller.signal); }
    finally { clearTimeout(timer); }
    const assessmentId = randomUUID();
    const client = await pool.connect();
    try {
      await client.query('BEGIN');
      await client.query('INSERT INTO web_assessments (id,web_scope_id,target_host,assessment_kind,results,created_by) VALUES ($1,$2,$3,\'web-passive\',$4::jsonb,$5)',
        [assessmentId, params.data.id, target.hostname, JSON.stringify(results), actor]);
      await audit(client, actor, 'web_assessment.completed', 'web_scope', params.data.id, { assessmentId, targetHost: target.hostname, kind: 'web-passive' }, request.id);
      await client.query('COMMIT');
    } catch (error) { await client.query('ROLLBACK'); throw error; }
    finally { client.release(); }
    return reply.code(201).send({ assessmentId, kind: 'web-passive', targetHost: target.hostname, checks: results, limitations: ['One HTTPS HEAD request to / only; no crawling, forms, authentication, or exploit attempts.', 'Findings are configuration observations, not vulnerability confirmation.'] });
  });

  app.post('/v1/web-scopes/:id/assess/email-dns', async (request, reply) => {
    if (!(await requireApi(request, reply))) return;
    const actor = await requireActor(request, reply);
    if (!actor) return;
    const params = webScopeParamsSchema.safeParse(request.params);
    const body = z.object({ domain: z.string().min(1).max(253) }).strict().safeParse(request.body);
    if (!params.success || !body.success) return reply.code(400).send({ error: 'invalid_email_domain' });
    const domain = body.data.domain.toLowerCase().replace(/\.$/, '');
    if (domain.includes('/') || domain.includes('@') || domain.includes(':') || domain.includes('*') || domain.includes('..')) return reply.code(400).send({ error: 'invalid_email_domain' });
    const scopeResult = await pool.query('SELECT * FROM web_scopes WHERE id=$1 AND disabled_at IS NULL', [params.data.id]);
    const scope = scopeResult.rows[0];
    if (!scope || new Date(String(scope.expires_at)).getTime() <= Date.now()) return reply.code(404).send({ error: 'active_web_scope_not_found' });
    if (!(scope.allowed_methods as string[]).includes('passive')) return reply.code(403).send({ error: 'passive_method_not_authorized' });
    const inScope = isWebTargetInScope(`https://${domain}/`, scope.approved_hosts as string[]);
    if (!inScope) return reply.code(403).send({ error: 'email_domain_not_authorized' });
    const recent = await pool.query("SELECT count(*)::integer AS n FROM web_assessments WHERE web_scope_id=$1 AND created_at > now() - interval '1 minute'", [params.data.id]);
    if (Number(recent.rows[0]?.n ?? 0) >= Number(scope.max_requests_per_minute)) return reply.code(429).send({ error: 'web_scope_rate_limit_reached' });
    const results = await assessMailDns(domain);
    const assessmentId = randomUUID();
    const client = await pool.connect();
    try {
      await client.query('BEGIN');
      await client.query('INSERT INTO web_assessments (id,web_scope_id,target_host,assessment_kind,results,created_by) VALUES ($1,$2,$3,\'email-dns\',$4::jsonb,$5)',
        [assessmentId, params.data.id, domain, JSON.stringify(results), actor]);
      await audit(client, actor, 'web_assessment.completed', 'web_scope', params.data.id, { assessmentId, targetHost: domain, kind: 'email-dns' }, request.id);
      await client.query('COMMIT');
    } catch (error) { await client.query('ROLLBACK'); throw error; }
    finally { client.release(); }
    return reply.code(201).send({ assessmentId, kind: 'email-dns', targetHost: domain, checks: results, limitations: ['DNS lookups only; no mail sent or mailbox accessed.', 'DKIM is not asserted because selectors require an authoritative selector list.'] });
  });

  app.get('/v1/web-scopes/:id/assessments', async (request, reply) => {
    if (!(await requireApi(request, reply))) return;
    const params = webScopeParamsSchema.safeParse(request.params);
    if (!params.success) return reply.code(400).send({ error: 'invalid_web_scope_id' });
    const result = await pool.query('SELECT id, target_host, assessment_kind, results, created_by, created_at FROM web_assessments WHERE web_scope_id=$1 ORDER BY created_at DESC LIMIT 200', [params.data.id]);
    return { assessments: result.rows };
  });

  app.post('/v1/scopes', async (request, reply) => {
    if (!(await requireCredential(request, reply, 'admin'))) return;
    const actor = await requireActor(request, reply);
    if (!actor) return;
    const parsed = scopeCreateSchema.safeParse(request.body);
    if (!parsed.success) return reply.code(400).send({ error: 'invalid_scope', issues: parsed.error.issues });
    if (Date.parse(parsed.data.expiresAt) <= Date.now()) return reply.code(400).send({ error: 'invalid_scope', message: 'Scope expiry must be in the future.' });
    const id = randomUUID();
    const data = parsed.data;
    const client = await pool.connect();
    try {
      await client.query('BEGIN');
      await client.query(
        `INSERT INTO authorized_scopes
         (id, program_slug, repository_url, source_commit, chain_id, target_addresses, required_fork_block,
          allowed_methods, program_authorization_ref, restrictions, expires_at, created_by)
         VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10::jsonb,$11,$12)`,
        [id, data.programSlug, data.repositoryUrl, data.sourceCommit.toLowerCase(), data.chainId,
          data.targetAddresses.map((x: string) => x.toLowerCase()), data.requiredForkBlock, data.allowedMethods,
          data.programAuthorizationRef, JSON.stringify(data.restrictions), data.expiresAt, actor],
      );
      await audit(client, actor, 'scope.registered', 'scope', id, { programSlug: data.programSlug, repositoryUrl: data.repositoryUrl, chainId: data.chainId, methodCount: data.allowedMethods.length }, request.id);
      await client.query('COMMIT');
      return reply.code(201).send({ id, status: 'registered', note: 'Registration records claimed authorization metadata; the operator must independently verify the cited Cantina rules before adding a scope.' });
    } catch (error) {
      await client.query('ROLLBACK');
      if (error && typeof error === 'object' && 'code' in error && error.code === '23505') return reply.code(409).send({ error: 'scope_already_registered' });
      throw error;
    } finally {
      client.release();
    }
  });

  app.post('/v1/target-records', async (request, reply) => {
    if (!(await requireCredential(request, reply, 'admin'))) return;
    const actor = await requireActor(request, reply);
    if (!actor) return;
    const parsed = targetRecordCreateSchema.safeParse(request.body);
    if (!parsed.success) return reply.code(400).send({ error: 'invalid_target_record', issues: parsed.error.issues });
    const scopeResult = await pool.query('SELECT * FROM authorized_scopes WHERE id=$1', [parsed.data.scopeId]);
    if (!scopeResult.rows[0]) return reply.code(404).send({ error: 'scope_not_found' });
    const scope = scopeFromDatabase(scopeResult.rows[0] as Record<string, unknown>);
    const digest = scopeBindingSha256(scope);
    const candidate = { ...parsed.data, programSlug: scope.programSlug, scopeSha256: digest };
    const decision = validateTargetRecord(candidate, scope);
    if (decision.outcome !== 'allow') return reply.code(403).send({ error: 'target_record_denied', oracle: decision });
    const id = randomUUID();
    const client = await pool.connect();
    try {
      await client.query('BEGIN');
      await client.query(`INSERT INTO target_records (id,scope_id,target_id,target_address,repository_url,source_commit,chain_id,fork_block,environment,allowed_methods,suite_ids,expires_at,scope_sha256,harness_sha256,created_by)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15)`,
      [id, parsed.data.scopeId, parsed.data.targetId, parsed.data.targetAddress.toLowerCase(), parsed.data.repositoryUrl, parsed.data.sourceCommit.toLowerCase(), parsed.data.chainId, parsed.data.forkBlock, parsed.data.environment, parsed.data.allowedMethods, parsed.data.suiteIds, parsed.data.expiresAt, digest, parsed.data.harnessSha256 ?? null, actor]);
      await audit(client, actor, 'target_record.created', 'target_record', id, { scopeId: parsed.data.scopeId, targetId: parsed.data.targetId, targetAddress: parsed.data.targetAddress, chainId: parsed.data.chainId, forkBlock: parsed.data.forkBlock }, request.id);
      await client.query('COMMIT');
    } catch (error) {
      await client.query('ROLLBACK');
      if (error && typeof error === 'object' && 'code' in error && error.code === '23505') return reply.code(409).send({ error: 'target_record_already_exists' });
      throw error;
    } finally {
      client.release();
    }
    return reply.code(201).send({ id, status: 'active', oracle: decision, authorizationSource: 'operator-registered scope; externally verified authorization is not implied' });
  });

  app.get('/v1/target-records', async (request, reply) => {
    if (!(await requireApi(request, reply))) return;
    const result = await pool.query(
      `SELECT t.*, s.program_slug FROM target_records t JOIN authorized_scopes s ON s.id=t.scope_id ORDER BY t.created_at DESC LIMIT 500`,
    );
    return { count: result.rowCount ?? 0, targetRecords: result.rows };
  });

  app.get('/v1/target-records/:id', async (request, reply) => {
    if (!(await requireApi(request, reply))) return;
    const params = idParamsSchema.safeParse(request.params);
    if (!params.success) return reply.code(400).send({ error: 'invalid_target_record_id' });
    const result = await pool.query(
      `SELECT t.*, s.program_slug FROM target_records t JOIN authorized_scopes s ON s.id=t.scope_id WHERE t.id=$1`,
      [params.data.id],
    );
    if (!result.rows[0]) return reply.code(404).send({ error: 'target_record_not_found' });
    return { targetRecord: result.rows[0] };
  });

  app.post('/v1/target-records/:id/revoke', async (request, reply) => {
    if (!(await requireCredential(request, reply, 'admin'))) return;
    const actor = await requireActor(request, reply);
    if (!actor) return;
    const params = idParamsSchema.safeParse(request.params);
    if (!params.success) return reply.code(400).send({ error: 'invalid_target_record_id' });
    const client = await pool.connect();
    try {
      await client.query('BEGIN');
      const updated = await client.query(
        "UPDATE target_records SET status='revoked', revoked_at=now() WHERE id=$1 AND status='active' RETURNING id, scope_id, target_id",
        [params.data.id],
      );
      if (!updated.rows[0]) {
        await client.query('ROLLBACK');
        return reply.code(404).send({ error: 'target_record_not_found_or_already_revoked' });
      }
      await audit(client, actor, 'target_record.revoked', 'target_record', params.data.id, { scopeId: updated.rows[0].scope_id, targetId: updated.rows[0].target_id }, request.id);
      await client.query('COMMIT');
      return reply.code(200).send({ id: params.data.id, status: 'revoked' });
    } catch (error) {
      await client.query('ROLLBACK');
      throw error;
    } finally {
      client.release();
    }
  });

  app.get('/v1/target-records/:id/check', async (request, reply) => {
    if (!(await requireApi(request, reply))) return;
    const params = idParamsSchema.safeParse(request.params);
    if (!params.success) return reply.code(400).send({ error: 'invalid_target_record_id' });
    const result = await pool.query(`SELECT t.*,s.program_slug,s.id AS loaded_scope_id,s.repository_url AS scope_repository_url,s.source_commit AS scope_source_commit,s.chain_id AS scope_chain_id,s.target_addresses AS scope_target_addresses,s.required_fork_block,s.allowed_methods AS scope_allowed_methods,s.program_authorization_ref,s.restrictions,s.expires_at AS scope_expires_at,s.disabled_at
      FROM target_records t JOIN authorized_scopes s ON s.id=t.scope_id WHERE t.id=$1`, [params.data.id]);
    if (!result.rows[0]) return reply.code(404).send({ error: 'target_record_not_found' });
    const row = result.rows[0] as Record<string, unknown>;
    const scope = scopeFromDatabase({ id: row.loaded_scope_id, program_slug: row.program_slug, repository_url: row.scope_repository_url, source_commit: row.scope_source_commit, chain_id: row.scope_chain_id, target_addresses: row.scope_target_addresses, required_fork_block: row.required_fork_block, allowed_methods: row.scope_allowed_methods, program_authorization_ref: row.program_authorization_ref, restrictions: row.restrictions, expires_at: row.scope_expires_at, disabled_at: row.disabled_at });
    const targetRecord = targetRecordFromDatabase({ ...row, program_slug: row.program_slug });
    const decision = validateTargetRecord(targetRecord, scope);
    return { targetRecordId: params.data.id, valid: decision.outcome === 'allow', oracle: decision };
  });

  app.post('/v1/workflows', async (request, reply) => {
    if (!(await requireApi(request, reply))) return;
    const actor = await requireActor(request, reply);
    if (!actor) return;
    const parsed = workflowCreateSchema.safeParse(request.body);
    if (!parsed.success) return reply.code(400).send({ error: 'invalid_workflow', issues: parsed.error.issues });
    const input = parsed.data;
    const bindingResult = await pool.query(`SELECT t.*,s.program_slug,s.id AS loaded_scope_id,s.repository_url AS scope_repository_url,s.source_commit AS scope_source_commit,s.chain_id AS scope_chain_id,s.target_addresses AS scope_target_addresses,s.required_fork_block,s.allowed_methods AS scope_allowed_methods,s.program_authorization_ref,s.restrictions,s.expires_at AS scope_expires_at,s.disabled_at
      FROM target_records t JOIN authorized_scopes s ON s.id=t.scope_id WHERE t.id=$1`, [input.targetRecordId]);
    if (!bindingResult.rows[0]) return reply.code(403).send({ error: 'target_record_required', workflowCreated: false });
    const binding = bindingResult.rows[0] as Record<string, unknown>;
    const scope = scopeFromDatabase({ id: binding.loaded_scope_id, program_slug: binding.program_slug, repository_url: binding.scope_repository_url, source_commit: binding.scope_source_commit, chain_id: binding.scope_chain_id, target_addresses: binding.scope_target_addresses, required_fork_block: binding.required_fork_block, allowed_methods: binding.scope_allowed_methods, program_authorization_ref: binding.program_authorization_ref, restrictions: binding.restrictions, expires_at: binding.scope_expires_at, disabled_at: binding.disabled_at });
    const target = targetRecordFromDatabase({ ...binding, program_slug: binding.program_slug });
    const targetDecision = validateTargetRecord(target, scope);
    const dispatchDecision = authorizeTargetDispatch(target, input);
    if (targetDecision.outcome !== 'allow' || dispatchDecision.outcome !== 'allow') return reply.code(403).send({ error: 'target_dispatch_denied', targetOracle: targetDecision, dispatchOracle: dispatchDecision, workflowCreated: false });
    const matched = scope as ScopeRecord;
    const scopeMatch = matchWorkflowToScope(input, matched);
    if (!scopeMatch.ok) return reply.code(403).send({ error: 'scope_denied', message: scopeMatch.reason, workflowCreated: false });

    const id = randomUUID();
    const client = await pool.connect();
    try {
      await client.query('BEGIN');
      await client.query(
        `INSERT INTO workflows (id, finding_id, title, scope_id, target_record_id, status, execution_status, source_commit, chain_id, fork_block, repository_url, target_addresses, requested_methods, created_by)
         VALUES ($1,$2,$3,$4,$5,'learning','queued',$6,$7,$8,$9,$10,$11,$12)`,
        [id, input.findingId ?? null, input.title, matched.id, target.id, input.sourceCommit.toLowerCase(), input.chainId, input.forkBlock,
          input.repositoryUrl, input.targetAddresses.map((x: string) => x.toLowerCase()), input.requestedMethods, actor],
      );
      await client.query(
        `INSERT INTO workflow_scope (workflow_id, scope_id, validated, validation_reason, validated_by) VALUES ($1,$2,true,'Exact scope match passed.', $3)`,
        [id, matched.id, actor],
      );
      await writeGate(client, id, 'G3', 'passed', [], 'scope-policy');
      await audit(client, actor, 'workflow.created', 'workflow', id, { scopeId: matched.id, targetRecordId: target.id, scopeBindingSha256: target.scopeSha256, findingId: input.findingId ?? null, requestedMethods: input.requestedMethods }, request.id);
      await client.query('COMMIT');
      return reply.code(201).send({ id, status: 'learning', executionStatus: 'queued', findingStatus: 'unverified', reviewStatus: 'pending', approvalStatus: 'not_requested', submissionStatus: 'not_ready' });
    } catch (error) {
      await client.query('ROLLBACK');
      throw error;
    } finally {
      client.release();
    }
  });

  app.get('/v1/workflows/:id', async (request, reply) => {
    if (!(await requireApi(request, reply))) return;
    const params = idParamsSchema.safeParse(request.params);
    if (!params.success) return reply.code(400).send({ error: 'invalid_id' });
    const workflowResult = await pool.query('SELECT * FROM workflows WHERE id=$1', [params.data.id]);
    const workflow = workflowResult.rows[0];
    if (!workflow) return reply.code(404).send({ error: 'workflow_not_found' });
    const [runs, evidence, gates, reviews, approvals, submissions] = await Promise.all([
      pool.query('SELECT id, target_record_id, suite_id, command_profile_id, status, source_commit, chain_id, fork_block, runner_id, exit_code, created_at, started_at, completed_at FROM execution_runs WHERE workflow_id=$1 ORDER BY created_at DESC', [params.data.id]),
      pool.query('SELECT id, target_record_id, artifact_id, evidence_kind, claim, source_ref, verified, verification_method, metadata, created_by, created_at FROM evidence WHERE workflow_id=$1 ORDER BY created_at DESC', [params.data.id]),
      pool.query('SELECT gate_id, outcome, reasons, evidence_ids, evaluated_by, evaluated_at FROM readiness_gate_results WHERE workflow_id=$1 ORDER BY gate_id', [params.data.id]),
      pool.query('SELECT id, target_record_id, decision, summary, evidence_ids, reviewer_id, created_at FROM review_decisions WHERE workflow_id=$1 ORDER BY created_at DESC', [params.data.id]),
      pool.query('SELECT id, target_record_id, approval_type, decision, rationale, artifact_id, approver_id, created_at FROM human_approvals WHERE workflow_id=$1 ORDER BY created_at DESC', [params.data.id]),
      pool.query('SELECT id, target_record_id, finding_id, report_artifact_id, status, external_submission_ref, created_by, created_at FROM submission_records WHERE workflow_id=$1 ORDER BY created_at DESC', [params.data.id]),
    ]);
    return { workflow, runs: runs.rows, evidence: evidence.rows, gates: gates.rows, reviews: reviews.rows, approvals: approvals.rows, submissions: submissions.rows };
  });

  app.get('/v1/workflows/:id/tasks', async (request, reply) => {
    if (!(await requireApi(request, reply))) return;
    const params = idParamsSchema.safeParse(request.params);
    if (!params.success) return reply.code(400).send({ error: 'invalid_id' });
    const result = await pool.query(
      `SELECT id, agent_id, target_record_id, status, input, output, error_summary, attempt, max_attempts, contract_version,
              available_at, lease_owner, lease_expires_at, created_at, updated_at
       FROM agent_tasks WHERE workflow_id=$1 ORDER BY created_at, id`, [params.data.id],
    );
    return { tasks: result.rows };
  });

  app.post('/v1/workflows/:id/tasks', async (request, reply) => {
    if (!(await requireApi(request, reply))) return;
    const actor = await requireActor(request, reply);
    if (!actor) return;
    const params = idParamsSchema.safeParse(request.params);
    const parsed = agentTaskCreateSchema.safeParse(request.body);
    if (!params.success || !parsed.success) return reply.code(400).send({ error: 'invalid_task_request', issues: parsed.success ? [] : parsed.error.issues });
    const workflowResult = await pool.query('SELECT target_record_id FROM workflows WHERE id=$1', [params.data.id]);
    if (!workflowResult.rows[0]) return reply.code(404).send({ error: 'workflow_not_found' });
    if (!workflowResult.rows[0].target_record_id) return reply.code(403).send({ error: 'target_record_missing_on_workflow' });
    if (parsed.data.targetRecordId && parsed.data.targetRecordId !== String(workflowResult.rows[0].target_record_id)) {
      return reply.code(403).send({ error: 'task_target_record_mismatch' });
    }
    const handler = BUILTIN_HANDLERS.get(parsed.data.agentId);
    if (!handler || handler.contractVersion !== parsed.data.contractVersion) return reply.code(422).send({ error: 'no_builtin_handler_for_contract', availableAgents: [...BUILTIN_HANDLERS.keys()] });
    const result = await enqueueAgentTask({ workflowId: params.data.id, ...parsed.data, targetRecordId: String(workflowResult.rows[0].target_record_id) });
    const client = await pool.connect();
    try {
      await client.query('BEGIN');
      await audit(client, actor, result.created ? 'agent_task.queued' : 'agent_task.reused', 'agent_task', result.id, { workflowId: params.data.id, targetRecordId: workflowResult.rows[0].target_record_id, agentId: parsed.data.agentId, idempotencyKey: parsed.data.idempotencyKey }, request.id);
      await client.query('COMMIT');
    } catch (error) { await client.query('ROLLBACK'); throw error; }
    finally { client.release(); }
    return reply.code(result.created ? 201 : 200).send({ taskId: result.id, created: result.created, dispatched: true, status: 'queued', worker: 'built-in-offline-analysis' });
  });

  app.post('/v1/workflows/:id/pipeline', async (request, reply) => {
    if (!(await requireApi(request, reply))) return;
    const actor = await requireActor(request, reply);
    if (!actor) return;
    const params = idParamsSchema.safeParse(request.params);
    const parsed = scoutPipelineSchema.safeParse(request.body);
    if (!params.success || !parsed.success) return reply.code(400).send({ error: 'invalid_scout_pipeline_request', issues: parsed.success ? [] : parsed.error.issues });
    const workflowResult = await pool.query('SELECT id,status,source_commit,scope_id,target_record_id FROM workflows WHERE id=$1', [params.data.id]);
    const workflow = workflowResult.rows[0];
    if (!workflow) return reply.code(404).send({ error: 'workflow_not_found' });
    if (!workflow.target_record_id) return reply.code(403).send({ error: 'target_record_missing_on_workflow' });
    if (String(workflow.status) !== 'analysis' || String(workflow.source_commit).toLowerCase() !== parsed.data.sourceCommit.toLowerCase()) return reply.code(409).send({ error: 'workflow_must_be_in_analysis_at_the_exact_pinned_commit' });
    const source = await pool.query("SELECT id FROM evidence WHERE workflow_id=$1 AND evidence_kind='source-manifest' AND verified=true LIMIT 1", [params.data.id]);
    if (!source.rows[0]) return reply.code(409).send({ error: 'verified_source_manifest_required' });
    const queued = await enqueueAgentTask({ workflowId: params.data.id, targetRecordId: String(workflow.target_record_id), agentId: 'pipeline-orchestrator', idempotencyKey: `scout-strategist:${parsed.data.sourceCommit.toLowerCase()}`, contractVersion: '1.0.0', input: parsed.data });
    const client = await pool.connect();
    try { await client.query('BEGIN'); await audit(client, actor, 'scout_strategist.dispatched', 'agent_task', queued.id, { workflowId: params.data.id, targetRecordId: workflow.target_record_id, sourceCommit: parsed.data.sourceCommit, created: queued.created }, request.id); await client.query('COMMIT'); }
    catch (error) { await client.query('ROLLBACK'); throw error; } finally { client.release(); }
    return reply.code(queued.created ? 202 : 200).send({ taskId: queued.id, created: queued.created, status: 'queued', dispatch: 'application-registered-offline-handlers', limitations: ['Source and AST are caller-supplied; the worker does not establish their authenticity.', 'Pattern matches are leads, not findings.'] });
  });

  app.post('/v1/workflows/:id/transition', async (request, reply) => {
    if (!(await requireCredential(request, reply, 'approval'))) return;
    const actor = await requireActor(request, reply);
    if (!actor) return;
    const params = idParamsSchema.safeParse(request.params);
    const parsed = transitionSchema.safeParse(request.body);
    if (!params.success || !parsed.success) return reply.code(400).send({ error: 'invalid_transition_request', issues: parsed.success ? [] : parsed.error.issues });
    const result = await pool.query('SELECT * FROM workflows WHERE id=$1', [params.data.id]);
    const workflow = result.rows[0];
    if (!workflow) return reply.code(404).send({ error: 'workflow_not_found' });
    const from = String(workflow.status) as WorkflowStatus;
    const to = parsed.data.to;
    try { assertTransition(from, to); }
    catch { return reply.code(409).send({ error: 'invalid_workflow_transition', from, to }); }

    if (from === 'learning' && to === 'analysis') {
      const gates = await pool.query("SELECT gate_id, outcome FROM readiness_gate_results WHERE workflow_id=$1 AND gate_id IN ('G1','G3')", [params.data.id]);
      const byGate = new Map(gates.rows.map((row) => [String(row.gate_id), String(row.outcome)]));
      const sourceEvidence = await pool.query("SELECT id FROM evidence WHERE workflow_id=$1 AND evidence_kind='source-manifest' AND verified=true LIMIT 1", [params.data.id]);
      if (!sourceEvidence.rows[0] || byGate.get('G1') !== 'passed' || byGate.get('G3') !== 'passed') return reply.code(409).send({ error: 'source_pin_and_scope_gates_required' });
    } else if (from === 'analysis' && to === 'approval_pending') {
      const analysisEvidence = await pool.query("SELECT id FROM evidence WHERE workflow_id=$1 AND evidence_kind IN ('analysis-result','static-analysis','source-excerpt') AND verified=true LIMIT 1", [params.data.id]);
      if (!analysisEvidence.rows[0]) return reply.code(409).send({ error: 'verified_analysis_evidence_required' });
    } else if (from === 'evidence_review' && to === 'impact_review') {
      if (String(workflow.finding_status) !== 'supported') return reply.code(409).send({ error: 'supported_finding_required' });
      const gates = await pool.query("SELECT gate_id, outcome FROM readiness_gate_results WHERE workflow_id=$1 AND gate_id IN ('G1','G2','G3','G4','G5','G6','G7','G8')", [params.data.id]);
      const byGate = new Map(gates.rows.map((row) => [String(row.gate_id), String(row.outcome)]));
      const missing = ['G1','G2','G3','G4','G5','G6','G7','G8'].filter((gateId) => !['passed','not_applicable'].includes(byGate.get(gateId) ?? 'inconclusive'));
      if (missing.length) return reply.code(409).send({ error: 'readiness_gates_incomplete', missingOrFailedGates: missing });
    } else if (from === 'impact_review' && to === 'independent_review') {
      if (String(workflow.finding_status) !== 'supported' || String(workflow.execution_status) !== 'passed') return reply.code(409).send({ error: 'supported_finding_and_passed_execution_required' });
    }
    const client = await pool.connect();
    try {
      await client.query('BEGIN');
      await client.query('UPDATE workflows SET status=$2, updated_at=now() WHERE id=$1', [params.data.id, to]);
      await audit(client, actor, 'workflow.transitioned', 'workflow', params.data.id, { from, to, reason: parsed.data.reason }, request.id);
      await client.query('COMMIT');
    } catch (error) { await client.query('ROLLBACK'); throw error; }
    finally { client.release(); }
    return { workflowId: params.data.id, from, to };
  });

  app.post('/v1/workflows/:id/source-pin', async (request, reply) => {
    if (!layerEnabled('source')) return reply.code(503).send({ error: 'workflow_layer_disabled', layer: 'source' });
    if (!(await requireCredential(request, reply, 'runner'))) return;
    const currentRunnerId = runnerIdentifier(request);
    const actor = 'runner:' + currentRunnerId;
    const params = idParamsSchema.safeParse(request.params);
    const body = manifestBodySchema.safeParse(request.body);
    if (!params.success || !body.success) return reply.code(400).send({ error: 'invalid_source_pin_request' });
    let bytes: Buffer;
    let raw: unknown;
    try {
      bytes = Buffer.from(body.data.manifestBase64, 'base64');
      if (bytes.byteLength > config.MAX_ARTIFACT_BYTES || bytes.toString('base64').replace(/=+$/, '') !== body.data.manifestBase64.replace(/=+$/, '')) return reply.code(400).send({ error: 'invalid_manifest_encoding_or_size' });
      raw = JSON.parse(bytes.toString('utf8')) as unknown;
    } catch {
      return reply.code(400).send({ error: 'invalid_manifest_json' });
    }
    const manifestParsed = sourceManifestSchema.safeParse(raw);
    if (!manifestParsed.success) return reply.code(400).send({ error: 'invalid_manifest_schema', issues: manifestParsed.error.issues });
    const manifest = manifestParsed.data;
    const seenPaths = new Set<string>();
    for (const file of manifest.trackedFiles) {
      if (!normalizeSourcePath(file.path)) return reply.code(400).send({ error: 'unsafe_source_path', path: file.path });
      if (seenPaths.has(file.path)) return reply.code(400).send({ error: 'duplicate_source_path', path: file.path });
      seenPaths.add(file.path);
    }
    const treeMaterial = manifest.trackedFiles.slice().sort((a: { path: string }, b: { path: string }) => a.path.localeCompare(b.path)).map((file: { path: string; sha256: string }) => `${file.path}\t${file.sha256.toLowerCase()}\n`).join('');
    const computedTree = sha256(Buffer.from(treeMaterial, 'utf8'));
    if (computedTree !== manifest.treeSha256.toLowerCase()) return reply.code(400).send({ error: 'source_tree_digest_mismatch' });

    const workflowResult = await pool.query('SELECT id, repository_url, source_commit, scope_id, target_record_id FROM workflows WHERE id=$1', [params.data.id]);
    const workflow = workflowResult.rows[0];
    if (!workflow) return reply.code(404).send({ error: 'workflow_not_found' });
    if (!workflow.target_record_id) return reply.code(403).send({ error: 'target_record_missing_on_workflow' });
    if (normalizeRepo(String(workflow.repository_url)) !== normalizeRepo(manifest.repositoryUrl) || String(workflow.source_commit).toLowerCase() !== manifest.commitSha.toLowerCase()) {
      return reply.code(409).send({ error: 'source_pin_mismatch' });
    }
    const stored = await putArtifact(bytes, sha256(bytes));
    const artifactId = randomUUID();
    const evidenceId = randomUUID();
    const client = await pool.connect();
    try {
      await client.query('BEGIN');
      await client.query(
        `INSERT INTO artifact_manifests (id, workflow_id, target_record_id, name, media_type, storage_key, sha256, byte_length, provenance, created_by)
         VALUES ($1,$2,$3,'source-manifest.json','application/json',$4,$5,$6,$7::jsonb,$8)
         ON CONFLICT (workflow_id, sha256) DO NOTHING`,
        [artifactId, params.data.id, workflow.target_record_id, stored.storageKey, stored.sha256, stored.byteLength, JSON.stringify({ manifestCommit: manifest.commitSha, trackedFileCount: manifest.trackedFiles.length, runnerId: currentRunnerId }), actor],
      );
      const actualArtifact = await client.query('SELECT id FROM artifact_manifests WHERE workflow_id=$1 AND sha256=$2', [params.data.id, stored.sha256]);
      const finalArtifactId = String(actualArtifact.rows[0].id);
      await client.query(
        `INSERT INTO evidence (id, workflow_id, target_record_id, artifact_id, evidence_kind, claim, source_ref, verified, verification_method, metadata, created_by)
         VALUES ($1,$2,$3,$4,'source-manifest','Manifest bytes and declared repository/commit/tree digest were checked; independent repository authenticity and source-line provenance are not yet attested.', $5::jsonb,false,NULL,$6::jsonb,$7)`,
        [evidenceId, params.data.id, workflow.target_record_id, finalArtifactId, JSON.stringify({ repositoryUrl: manifest.repositoryUrl, commitSha: manifest.commitSha }), JSON.stringify({ targetRecordId: workflow.target_record_id, treeSha256: computedTree, trackedFileCount: manifest.trackedFiles.length, caveat: 'Authenticity relies on the separately controlled runner; this API does not independently fetch the repository.' }), actor],
      );
      await writeGate(client, params.data.id, 'G1', 'inconclusive', ['Manifest format/tree digest and workflow commit binding checked. G1 remains inconclusive until verified independent source-attestation evidence establishes repository identity, commit object, and source-line provenance.'], 'source-manifest-validator', [evidenceId]);
      await audit(client, actor, 'source_manifest.validated_g1_inconclusive', 'workflow', params.data.id, { artifactId: finalArtifactId, evidenceId, commitSha: manifest.commitSha, treeSha256: computedTree }, request.id);
      await client.query('COMMIT');
      return reply.code(201).send({ artifactId: finalArtifactId, evidenceId, treeSha256: computedTree, trackedFileCount: manifest.trackedFiles.length, verification: 'manifest integrity checked; G1 remains inconclusive pending independently reviewed source-attestation evidence' });
    } catch (error) {
      await client.query('ROLLBACK');
      throw error;
    } finally {
      client.release();
    }
  });

  app.post('/v1/workflows/:id/artifacts', async (request, reply) => {
    if (!(await requireCredential(request, reply, 'runner'))) return;
    const currentRunnerId = runnerIdentifier(request);
    const params = idParamsSchema.safeParse(request.params);
    const parsed = artifactUploadSchema.safeParse(request.body);
    if (!params.success || !parsed.success) return reply.code(400).send({ error: 'invalid_artifact_upload', issues: parsed.success ? [] : parsed.error.issues });
    const workflow = await pool.query('SELECT id, target_record_id FROM workflows WHERE id=$1', [params.data.id]);
    if (!workflow.rows[0]) return reply.code(404).send({ error: 'workflow_not_found' });
    if (!workflow.rows[0].target_record_id) return reply.code(403).send({ error: 'target_record_missing_on_workflow' });
    if (parsed.data.targetRecordId && parsed.data.targetRecordId !== String(workflow.rows[0].target_record_id)) return reply.code(409).send({ error: 'artifact_target_binding_mismatch' });
    if (config.NODE_ENV === 'production') {
      const leaseToken = request.headers['x-run-lease-token'];
      const assigned = await pool.query("SELECT 1 FROM execution_runs WHERE workflow_id=$1 AND runner_id=$2 AND lease_token=$3 AND status='running' AND lease_expires_at > now() LIMIT 1", [params.data.id, currentRunnerId, leaseToken]);
      if (!assigned.rows[0]) return reply.code(403).send({ error: 'runner_has_no_active_lease_for_workflow' });
    }
    let bytes: Buffer;
    try {
      bytes = Buffer.from(parsed.data.contentBase64, 'base64');
      if (bytes.byteLength > config.MAX_ARTIFACT_BYTES || bytes.toString('base64').replace(/=+$/, '') !== parsed.data.contentBase64.replace(/=+$/, '')) return reply.code(400).send({ error: 'invalid_artifact_encoding_or_size' });
    } catch { return reply.code(400).send({ error: 'invalid_artifact_encoding' }); }
    let stored: Awaited<ReturnType<typeof putArtifact>>;
    try { stored = await putArtifact(bytes, parsed.data.expectedSha256); }
    catch (error) { return reply.code(400).send({ error: 'artifact_integrity_error', message: errorMessage(error) }); }
    const artifactId = randomUUID();
    const actor = `runner:${currentRunnerId}`;
    const client = await pool.connect();
    let existing: { rows: Array<Record<string, unknown>> };
    try {
      await client.query('BEGIN');
      await client.query(
        `INSERT INTO artifact_manifests (id, workflow_id, target_record_id, name, media_type, storage_key, sha256, byte_length, provenance, created_by)
         VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9::jsonb,$10)
         ON CONFLICT (workflow_id, sha256) DO NOTHING`,
        [artifactId, params.data.id, workflow.rows[0].target_record_id, parsed.data.name, parsed.data.mediaType, stored.storageKey, stored.sha256, stored.byteLength, JSON.stringify({ source: 'runner-upload', runnerId: currentRunnerId, targetRecordId: workflow.rows[0].target_record_id }), actor],
      );
      existing = await client.query('SELECT id, storage_key, sha256, byte_length FROM artifact_manifests WHERE workflow_id=$1 AND sha256=$2', [params.data.id, stored.sha256]);
      await audit(client, actor, 'artifact.uploaded', 'artifact', String(existing.rows[0]?.id), { workflowId: params.data.id, targetRecordId: workflow.rows[0].target_record_id, sha256: stored.sha256, byteLength: stored.byteLength, mediaType: parsed.data.mediaType }, request.id);
      await client.query('COMMIT');
    } catch (error) { await client.query('ROLLBACK'); throw error; }
    finally { client.release(); }
    return reply.code(201).send({ artifactId: existing!.rows[0]!.id, storageKey: existing!.rows[0]!.storage_key, sha256: stored.sha256, byteLength: stored.byteLength, duplicateContent: String(existing!.rows[0]!.id) !== artifactId });
  });

  app.post('/v1/workflows/:id/evidence', async (request, reply) => {
    if (!(await requireCredential(request, reply, 'runner'))) return;
    const params = idParamsSchema.safeParse(request.params);
    const parsed = evidenceCreateSchema.safeParse(request.body);
    if (!params.success || !parsed.success) return reply.code(400).send({ error: 'invalid_evidence_annotation', issues: parsed.success ? [] : parsed.error.issues });
    const artifact = await pool.query('SELECT id, sha256, target_record_id FROM artifact_manifests WHERE id=$1 AND workflow_id=$2', [parsed.data.artifactId, params.data.id]);
    if (!artifact.rows[0]) return reply.code(404).send({ error: 'workflow_artifact_not_found' });
    const workflow = await pool.query('SELECT id, target_record_id FROM workflows WHERE id=$1', [params.data.id]);
    if (!workflow.rows[0]) return reply.code(404).send({ error: 'workflow_not_found' });
    if (!workflow.rows[0].target_record_id) return reply.code(403).send({ error: 'target_record_missing_on_workflow' });
    if (parsed.data.targetRecordId && parsed.data.targetRecordId !== String(workflow.rows[0].target_record_id)) return reply.code(409).send({ error: 'evidence_target_binding_mismatch' });
    const targetBinding = bindEvidenceToTarget(String(workflow.rows[0].target_record_id ?? ''), artifact.rows[0].target_record_id ? String(artifact.rows[0].target_record_id) : null);
    if (targetBinding.outcome !== 'allow') return reply.code(409).send({ error: 'evidence_target_binding_mismatch', oracle: targetBinding });
    const evidenceId = randomUUID();
    const currentRunnerId = runnerIdentifier(request);
    const actor = `runner:${currentRunnerId}`;
    const client = await pool.connect();
    try {
      await client.query('BEGIN');
      await client.query(
        `INSERT INTO evidence (id, workflow_id, target_record_id, artifact_id, evidence_kind, claim, source_ref, verified, metadata, created_by)
         VALUES ($1,$2,$3,$4,$5,$6,$7::jsonb,false,$8::jsonb,$9)`,
        [evidenceId, params.data.id, workflow.rows[0].target_record_id, parsed.data.artifactId, parsed.data.evidenceKind, parsed.data.claim, JSON.stringify(parsed.data.sourceRef), JSON.stringify({ ...parsed.data.metadata, targetRecordId: workflow.rows[0].target_record_id, artifactSha256: artifact.rows[0].sha256 }), actor],
      );
      await audit(client, actor, 'evidence.annotation_created', 'evidence', evidenceId, { workflowId: params.data.id, targetRecordId: workflow.rows[0].target_record_id, artifactId: parsed.data.artifactId, evidenceKind: parsed.data.evidenceKind }, request.id);
      await client.query('COMMIT');
    } catch (error) { await client.query('ROLLBACK'); throw error; }
    finally { client.release(); }
    return reply.code(201).send({ evidenceId, verified: false, message: 'Evidence annotation is unverified until a human reviewer checks the referenced artifact.' });
  });

  app.post('/v1/workflows/:id/evidence/:evidenceId/verify', async (request, reply) => {
    if (!(await requireCredential(request, reply, 'approval'))) return;
    const actor = await requireActor(request, reply);
    if (!actor) return;
    const params = z.object({ id: z.string().uuid(), evidenceId: z.string().uuid() }).safeParse(request.params);
    const parsed = evidenceVerifySchema.safeParse(request.body);
    if (!params.success || !parsed.success) return reply.code(400).send({ error: 'invalid_evidence_verification', issues: parsed.success ? [] : parsed.error.issues });
    const result = await pool.query(
      `SELECT e.id, e.verified, e.artifact_id, e.target_record_id, a.target_record_id AS artifact_target_record_id,
              w.target_record_id AS workflow_target_record_id, w.created_by, a.storage_key, a.sha256, a.byte_length
       FROM evidence e JOIN artifact_manifests a ON a.id=e.artifact_id
       JOIN workflows w ON w.id=e.workflow_id
       WHERE e.id=$1 AND e.workflow_id=$2`, [params.data.evidenceId, params.data.id],
    );
    const row = result.rows[0];
    if (!row) return reply.code(404).send({ error: 'evidence_not_found' });
    const binding = bindEvidenceToTarget(String(row.workflow_target_record_id ?? ''), row.target_record_id ? String(row.target_record_id) : null);
    if (binding.outcome !== 'allow' || row.artifact_target_record_id !== row.target_record_id) return reply.code(409).send({ error: 'evidence_target_binding_mismatch', oracle: binding });
    const reviewerDecision = validateIndependentHumanReview(String(row.created_by), actor);
    if (reviewerDecision.outcome !== 'allow') return reply.code(403).send({ error: 'independent_evidence_verifier_required', oracle: reviewerDecision });
    try {
      const bytes = await loadArtifactByStorageKey(String(row.storage_key));
      if (sha256(bytes) !== String(row.sha256) || bytes.byteLength !== Number(row.byte_length)) return reply.code(409).send({ error: 'artifact_integrity_failed' });
    } catch { return reply.code(409).send({ error: 'artifact_not_retrievable_or_corrupt' }); }
    const client = await pool.connect();
    try {
      await client.query('BEGIN');
      await client.query("UPDATE evidence SET verified=true, verification_method='human-artifact-review', metadata=metadata || $2::jsonb WHERE id=$1", [params.data.evidenceId, JSON.stringify({ humanVerificationRationale: parsed.data.rationale })]);
      await audit(client, actor, 'evidence.verified', 'evidence', params.data.evidenceId, { workflowId: params.data.id, targetRecordId: row.workflow_target_record_id, artifactId: row.artifact_id, sha256: row.sha256, rationale: parsed.data.rationale }, request.id);
      await client.query('COMMIT');
    } catch (error) { await client.query('ROLLBACK'); throw error; }
    finally { client.release(); }
    return { evidenceId: params.data.evidenceId, verified: true, verificationMethod: 'human-artifact-review' };
  });

  app.post('/v1/workflows/:id/gates/:gateId/evaluate', async (request, reply) => {
    if (!layerEnabled('evidence')) return reply.code(503).send({ error: 'workflow_layer_disabled', layer: 'evidence' });
    if (!(await requireCredential(request, reply, 'approval'))) return;
    const actor = await requireActor(request, reply);
    if (!actor) return;
    const params = z.object({ id: z.string().uuid(), gateId: z.enum(['G1','G2','G4','G5','G6','G7']) }).safeParse(request.params);
    const parsed = gateEvaluationSchema.safeParse(request.body);
    if (!params.success || !parsed.success) return reply.code(400).send({ error: 'invalid_gate_evaluation', issues: parsed.success ? [] : parsed.error.issues });
    const workflowResult = await pool.query('SELECT id, target_record_id, requested_methods, repository_url, source_commit FROM workflows WHERE id=$1', [params.data.id]);
    const workflow = workflowResult.rows[0];
    if (!workflow) return reply.code(404).send({ error: 'workflow_not_found' });
    if (!workflow.target_record_id) return reply.code(403).send({ error: 'target_record_missing_on_workflow' });
    if (parsed.data.outcome === 'passed') {
      if (!parsed.data.evidenceIds.length) return reply.code(409).send({ error: 'gate_evidence_required' });
      const ev = await pool.query('SELECT id, evidence_kind, metadata FROM evidence WHERE workflow_id=$1 AND target_record_id=$2 AND id=ANY($3::uuid[]) AND verified=true', [params.data.id, workflow.target_record_id, parsed.data.evidenceIds]);
      if ((ev.rowCount ?? 0) !== parsed.data.evidenceIds.length) return reply.code(409).send({ error: 'gate_evidence_unverified_or_foreign' });
      if (params.data.gateId === 'G1') {
        const check = validateSourceAttestationEvidence(ev.rows as Array<{ evidence_kind: string; metadata: unknown }>, String(workflow.repository_url), String(workflow.source_commit));
        if (!check.ok) return reply.code(409).send({ error: 'independent_source_attestation_required', message: check.reason });
      } else if (params.data.gateId === 'G2') {
        const observations = ev.rows.filter((row) => row.evidence_kind === 'rpc-observation');
        const providers = new Set(observations.map((row) => String((row.metadata as Record<string, unknown>).providerId ?? '')));
        const digests = new Set(observations.map((row) => String((row.metadata as Record<string, unknown>).stateDigest ?? '')));
        if (observations.length < 2 || providers.size < 2 || providers.has('') || digests.size !== 1 || digests.has('')) return reply.code(409).send({ error: 'rpc_cross_provider_evidence_invalid', message: 'G2 requires at least two verified provider observations with distinct provider IDs and a matching non-empty stateDigest.' });
      } else if (params.data.gateId === 'G4') {
        if (!ev.rows.some((row) => row.evidence_kind === 'overlap-review' && Number((row.metadata as Record<string, unknown>).sourcesExamined) > 0)) return reply.code(409).send({ error: 'overlap_coverage_evidence_required' });
      } else if (params.data.gateId === 'G5') {
        if (!ev.rows.some((row) => row.evidence_kind === 'severity-review' && typeof (row.metadata as Record<string, unknown>).rubricVersion === 'string' && String((row.metadata as Record<string, unknown>).rubricVersion).length > 0)) return reply.code(409).send({ error: 'severity_rubric_evidence_required' });
      } else if (params.data.gateId === 'G6') {
        const hasSource = ev.rows.some((row) => row.evidence_kind === 'source-manifest');
        const hasExecution = ev.rows.some((row) => ['execution-output','trace','impact-measurement','symbolic-analysis','counterexample'].includes(String(row.evidence_kind)));
        if (!hasSource || !hasExecution) return reply.code(409).send({ error: 'claim_provenance_evidence_required', message: 'G6 requires verified source provenance and verified execution/analysis evidence among the selected records.' });
      } else if (params.data.gateId === 'G7') {
        if (!ev.rows.some((row) => ['symbolic-analysis','counterexample'].includes(String(row.evidence_kind)))) return reply.code(409).send({ error: 'symbolic_or_counterexample_evidence_required' });
      }
    } else if (parsed.data.outcome === 'not_applicable') {
      const methods = workflow.requested_methods as string[];
      if (params.data.gateId === 'G1') return reply.code(409).send({ error: 'gate_cannot_be_skipped', message: 'G1 source authenticity and line provenance is mandatory.' });
      if (params.data.gateId === 'G2' && methods.includes('fork-test')) return reply.code(409).send({ error: 'gate_cannot_be_skipped', message: 'G2 is required when fork-test is in the workflow.' });
      if (!/approved policy|program rule|not applicable/i.test(parsed.data.rationale)) return reply.code(400).send({ error: 'policy_basis_required_for_not_applicable' });
    }
    const client = await pool.connect();
    try {
      await client.query('BEGIN');
      await writeGate(client, params.data.id, params.data.gateId, parsed.data.outcome, [parsed.data.rationale], actor, parsed.data.evidenceIds);
      await audit(client, actor, 'readiness_gate.evaluated', 'workflow', params.data.id, { gateId: params.data.gateId, targetRecordId: workflow.target_record_id, outcome: parsed.data.outcome, evidenceIds: parsed.data.evidenceIds, rationale: parsed.data.rationale }, request.id);
      await client.query('COMMIT');
    } catch (error) { await client.query('ROLLBACK'); throw error; }
    finally { client.release(); }
    return reply.code(201).send({ workflowId: params.data.id, gateId: params.data.gateId, outcome: parsed.data.outcome, evidenceIds: parsed.data.evidenceIds });
  });

  app.post('/v1/workflows/:id/approve-run', async (request, reply) => {
    if (!layerEnabled('execution')) return reply.code(503).send({ error: 'workflow_layer_disabled', layer: 'execution' });
    if (!(await requireCredential(request, reply, 'approval'))) return;
    const actor = await requireActor(request, reply);
    if (!actor) return;
    const params = idParamsSchema.safeParse(request.params);
    const parsed = approveRunSchema.safeParse(request.body);
    if (!params.success || !parsed.success) return reply.code(400).send({ error: 'invalid_run_approval', issues: parsed.success ? [] : parsed.error.issues });
    const suite = getSuite(parsed.data.suiteId);
    if (!suite) return reply.code(400).send({ error: 'unknown_suite', message: 'Suite ID is not allowlisted.' });
    if (!suite.dispatchEnabled) return reply.code(501).send({ error: 'suite_has_no_automatic_runner_profile' });
    const result = await pool.query(
      `SELECT w.*, s.expires_at, s.allowed_methods, s.disabled_at FROM workflows w
       JOIN authorized_scopes s ON s.id=w.scope_id WHERE w.id=$1`, [params.data.id],
    );
    const workflow = result.rows[0];
    if (!workflow) return reply.code(404).send({ error: 'workflow_not_found' });
    if (workflow.disabled_at || new Date(String(workflow.expires_at)).getTime() <= Date.now()) return reply.code(403).send({ error: 'scope_expired_or_disabled' });
    if (!workflow.target_record_id) return reply.code(403).send({ error: 'target_record_missing_on_workflow' });
    if (parsed.data.targetRecordId && parsed.data.targetRecordId !== String(workflow.target_record_id)) return reply.code(409).send({ error: 'target_record_mismatch' });
    const targetResult = await pool.query(`SELECT t.*,s.program_slug FROM target_records t JOIN authorized_scopes s ON s.id=t.scope_id WHERE t.id=$1 AND t.scope_id=$2`, [workflow.target_record_id, workflow.scope_id]);
    if (!targetResult.rows[0]) return reply.code(403).send({ error: 'target_record_missing' });
    const currentScopeResult = await pool.query('SELECT * FROM authorized_scopes WHERE id=$1', [workflow.scope_id]);
    const targetOracle = validateTargetRecord(targetRecordFromDatabase(targetResult.rows[0] as Record<string, unknown>), scopeFromDatabase(currentScopeResult.rows[0] as Record<string, unknown>));
    const profileOracle = selectVerificationProfile(targetRecordFromDatabase(targetResult.rows[0] as Record<string, unknown>), parsed.data.suiteId);
    if (targetOracle.outcome !== 'allow' || profileOracle.outcome !== 'allow') return reply.code(403).send({ error: 'verification_profile_denied', targetOracle, profileOracle });
    const currentStatus = String(workflow.status) as WorkflowStatus;
    if (currentStatus !== 'approval_pending' && currentStatus !== 'execution') return reply.code(409).send({ error: 'workflow_not_ready_for_execution', status: currentStatus });
    if (currentStatus === 'approval_pending') { try { assertTransition(currentStatus, 'execution'); } catch { return reply.code(409).send({ error: 'invalid_workflow_transition' }); } }
    const requestedMethods = workflow.requested_methods as string[];
    const allowedMethods = workflow.allowed_methods as string[];
    if (!requestedMethods.includes(suite.requiredMethod) || !allowedMethods.includes(suite.requiredMethod)) return reply.code(403).send({ error: 'suite_method_not_authorized' });
    const srcEvidence = await pool.query("SELECT id FROM evidence WHERE workflow_id=$1 AND evidence_kind='source-manifest' AND verified=true LIMIT 1", [params.data.id]);
    if (!srcEvidence.rows[0]) return reply.code(409).send({ error: 'source_pin_required', message: 'A validated source manifest is required before queueing tests.' });
    if (suite.requiredMethod === 'fork-test' && Number(workflow.fork_block) <= 0) return reply.code(403).send({ error: 'fork_block_missing' });
    const runId = randomUUID();
    const approvalId = randomUUID();
    const client = await pool.connect();
    try {
      await client.query('BEGIN');
      await client.query(
        `INSERT INTO human_approvals (id, workflow_id, target_record_id, approval_type, decision, rationale, approver_id)
         VALUES ($1,$2,$3,'run','approved',$4,$5)`, [approvalId, params.data.id, workflow.target_record_id, parsed.data.rationale, actor],
      );
      await client.query(
        `INSERT INTO execution_runs (id, workflow_id, target_record_id, suite_id, command_profile_id, status, repository_url, source_commit, chain_id, fork_block, approved_by, approval_rationale)
         VALUES ($1,$2,$3,$4,$5,'queued',$6,$7,$8,$9,$10,$11)`,
        [runId, params.data.id, workflow.target_record_id, suite.id, suite.commandProfileId, workflow.repository_url, workflow.source_commit, workflow.chain_id, workflow.fork_block, actor, parsed.data.rationale],
      );
      await client.query("UPDATE workflows SET status='execution', approval_status='approved', execution_status='queued', updated_at=now() WHERE id=$1", [params.data.id]);
      await audit(client, actor, 'run.queue_approved', 'execution_run', runId, { workflowId: params.data.id, targetRecordId: workflow.target_record_id, suiteId: suite.id, dispatched: true }, request.id);
      await client.query('COMMIT');
    } catch (error) {
      await client.query('ROLLBACK');
      throw error;
    } finally { client.release(); }
    return reply.code(202).send({ runId, suiteId: suite.id, status: 'queued', dispatchState: 'isolated-runner-poll-queue', executed: false, message: 'Human approval recorded. A registered isolated runner must claim the run; no command has executed yet.' });
  });

  app.post('/v1/workflows/:id/runs/:runId/receipt', async (request, reply) => {
    if (!(await requireCredential(request, reply, 'runner'))) return;
    const currentRunnerId = runnerIdentifier(request);
    const params = runParamsSchema.safeParse(request.params);
    const receiptParsed = executionReceiptSchema.safeParse(request.body);
    if (!params.success || !receiptParsed.success) return reply.code(400).send({ error: 'invalid_execution_receipt', issues: receiptParsed.success ? [] : receiptParsed.error.issues });
    const receipt = receiptParsed.data as ExecutionReceipt;
    if (receipt.runId !== params.data.runId) return reply.code(409).send({ error: 'receipt_run_id_mismatch' });
    const result = await pool.query(
      `SELECT r.*, w.status AS workflow_status, w.target_record_id AS workflow_target_record_id FROM execution_runs r JOIN workflows w ON w.id=r.workflow_id WHERE r.id=$1 AND r.workflow_id=$2`,
      [params.data.runId, params.data.id],
    );
    const run = result.rows[0];
    if (!run) return reply.code(404).send({ error: 'run_not_found' });
    if (!run.target_record_id || String(run.target_record_id) !== String(run.workflow_target_record_id)) return reply.code(409).send({ error: 'target_record_mismatch_on_run' });
    if (receipt.targetRecordId !== String(run.target_record_id)) return reply.code(409).send({ error: 'receipt_target_record_mismatch' });
    if (String(run.status) !== 'queued' && String(run.status) !== 'running') return reply.code(409).send({ error: 'run_not_receivable', status: run.status });
    if (config.NODE_ENV === 'production' && (String(run.status) !== 'running' || String(run.runner_id) !== currentRunnerId || String(run.lease_token) !== String(request.headers['x-run-lease-token']) || !run.lease_expires_at || new Date(String(run.lease_expires_at)).getTime() <= Date.now())) return reply.code(409).send({ error: 'runner_lease_missing_expired_or_mismatched' });
    if (String(run.runner_id ?? currentRunnerId) !== currentRunnerId) return reply.code(403).send({ error: 'run_assigned_to_different_runner' });
    if (String(run.workflow_status) !== 'execution') return reply.code(409).send({ error: 'workflow_not_in_execution_stage', status: run.workflow_status });
    const suite = getSuite(String(run.suite_id));
    if (!suite) return reply.code(500).send({ error: 'suite_registry_inconsistent' });
    const artifactUris = [receipt.logArtifact, ...receipt.artifacts];
    if (artifactUris.some((artifact) => !/^sha256\/[a-f0-9]{2}\/[a-f0-9]{64}$/i.test(artifact.uri))) return reply.code(400).send({ error: 'invalid_artifact_uri', message: 'Receipt artifact URIs must reference content-addressed uploads from this API.' });
    const registeredArtifacts = await pool.query('SELECT storage_key, sha256, byte_length, target_record_id FROM artifact_manifests WHERE workflow_id=$1', [params.data.id]);
    const registeredByKey = new Map(registeredArtifacts.rows.map((row) => [String(row.storage_key), row]));
    for (const artifact of artifactUris) {
      const stored = registeredByKey.get(artifact.uri);
      if (!stored || bindEvidenceToTarget(String(run.target_record_id ?? ''), stored.target_record_id ? String(stored.target_record_id) : null).outcome !== 'allow' || String(stored.sha256).toLowerCase() !== artifact.sha256.toLowerCase() || Number(stored.byte_length) !== artifact.byteLength) {
        return reply.code(409).send({ error: 'artifact_not_registered_for_workflow', artifactName: artifact.name });
      }
    }
    const runnerKey = config.NODE_ENV === 'production'
      ? await pool.query('SELECT public_key_pem,allowed_suites FROM runner_identities WHERE runner_id=$1 AND enabled=true', [currentRunnerId])
      : undefined;
    if (config.NODE_ENV === 'production' && (!runnerKey?.rows[0] || !(runnerKey.rows[0].allowed_suites as string[]).includes(String(run.suite_id)))) return reply.code(403).send({ error: 'runner_not_authorized_for_suite' });
    const checks = await verifyExecutionReceipt(receipt, {
      runId: String(run.id), targetRecordId: String(run.target_record_id), suiteId: String(run.suite_id), repositoryUrl: String(run.repository_url), sourceCommit: String(run.source_commit),
      chainId: Number(run.chain_id), forkBlock: Number(run.fork_block), commandProfileId: String(run.command_profile_id), requiredAssertions: suite.requiredAssertions,
    }, suite, currentRunnerId,
    config.NODE_ENV === 'production'
      ? { ed25519PublicKeyPem: String(runnerKey?.rows[0]?.public_key_pem) }
      : config.RUNNER_PUBLIC_KEY_PEM
        ? { ed25519PublicKeyPem: config.RUNNER_PUBLIC_KEY_PEM }
        : config.RUNNER_TOKEN,
    { load: loadArtifactByStorageKey });
    const passed = checks.every((check) => check.outcome === 'passed');
    const newStatus = passed ? 'passed' : 'failed';
    const client = await pool.connect();
    try {
      await client.query('BEGIN');
      await client.query(
        `UPDATE execution_runs SET status=$2, runner_id=$3, receipt=$4::jsonb, exit_code=$5, started_at=$6, completed_at=$7 WHERE id=$1`,
        [String(run.id), newStatus, receipt.runnerId, JSON.stringify(receipt), receipt.exitCode, receipt.startedAt, receipt.completedAt],
      );
      await client.query('UPDATE workflows SET execution_status=$2, updated_at=now() WHERE id=$1', [params.data.id, newStatus]);
      const existingArtifacts = await client.query('SELECT id, storage_key, sha256, name, media_type, byte_length, target_record_id FROM artifact_manifests WHERE workflow_id=$1', [params.data.id]);
      const byStorageKey = new Map(existingArtifacts.rows.map((row) => [String(row.storage_key), row]));
      for (const artifact of artifactUris) {
        const known = byStorageKey.get(artifact.uri);
        if (known && String(known.sha256).toLowerCase() === artifact.sha256.toLowerCase()) {
          if (bindEvidenceToTarget(String(run.target_record_id), known.target_record_id ? String(known.target_record_id) : null).outcome === 'allow') {
            await client.query(
              `INSERT INTO evidence (id, workflow_id, target_record_id, artifact_id, evidence_kind, claim, source_ref, verified, verification_method, metadata, created_by)
               VALUES ($1,$2,$3,$4,$5,$6,$7::jsonb,$8,$9,$10::jsonb,$11) ON CONFLICT DO NOTHING`,
              [randomUUID(), params.data.id, run.target_record_id, known.id, artifact.name.toLowerCase().includes('trace') ? 'trace' : 'execution-output', `Runner artifact ${artifact.name} hash verified as part of receipt evaluation.`, JSON.stringify({ runId: run.id, uri: artifact.uri }), passed, 'signed-runner-receipt-v1', JSON.stringify({ checks, targetRecordId: run.target_record_id }), `runner:${currentRunnerId}`],
            );
          }
        }
      }
      const identityCheck = checks.find((check) => check.id === 'receipt_identity');
      const signatureCheck = checks.find((check) => check.id === 'receipt_signature');
      const artifactCheck = checks.find((check) => check.id === 'artifact_integrity');
      const integrityChecks = checks.filter((check) => ['receipt_identity','receipt_signature','artifact_integrity'].includes(check.id));
      const integrityPassed = integrityChecks.length === 3 && integrityChecks.every((check) => check.outcome === 'passed');
      // Receipt-integrity status is preserved in the run response/audit; G6 remains a broader human-reviewed claim-provenance gate.
      // G8 is only passed when baseline, positive reproduction, and patched negative control all passed.
      const statusResult = await client.query('SELECT suite_id, status FROM execution_runs WHERE workflow_id=$1 ORDER BY created_at DESC, id DESC', [params.data.id]);
      const latestBySuite = new Map<string, string>();
      for (const row of statusResult.rows) {
        const suiteId = String(row.suite_id);
        if (!latestBySuite.has(suiteId)) latestBySuite.set(suiteId, String(row.status));
      }
      const requiredControls = ['baseline-tests','revocation','patched-negative-control'];
      const missingControls = requiredControls.filter((suiteId) => !latestBySuite.has(suiteId));
      const failedControls = requiredControls.filter((suiteId) => ['failed','timed_out','cancelled'].includes(latestBySuite.get(suiteId) ?? ''));
      const controlsPassed = missingControls.length === 0 && requiredControls.every((suiteId) => latestBySuite.get(suiteId) === 'passed');
      await writeGate(client, params.data.id, 'G8', controlsPassed ? 'passed' : failedControls.length ? 'failed' : 'inconclusive', controlsPassed ? [] : [...missingControls.map((suiteId) => `Missing required control suite: ${suiteId}`), ...failedControls.map((suiteId) => `Latest result for ${suiteId} is ${latestBySuite.get(suiteId)}.`)], `runner:${currentRunnerId}`);
      const outstanding = statusResult.rows.filter((row) => row.status === 'queued' || row.status === 'running');
      const latestStatuses = [...latestBySuite.values()];
      const aggregateStatus = outstanding.some((row) => row.status === 'running') ? 'running'
        : outstanding.length ? 'queued'
        : latestStatuses.includes('timed_out') ? 'timed_out'
        : latestStatuses.includes('failed') ? 'failed'
        : latestStatuses.length > 0 && latestStatuses.every((status) => status === 'passed') ? 'passed'
        : newStatus;
      await client.query("UPDATE workflows SET execution_status=$2, status=CASE WHEN $3 THEN 'evidence_review' ELSE status END, updated_at=now() WHERE id=$1", [params.data.id, aggregateStatus, outstanding.length === 0]);
      await audit(client, `runner:${currentRunnerId}`, 'execution.receipt_processed', 'execution_run', String(run.id), { workflowId: params.data.id, targetRecordId: run.target_record_id, passed, checks, identityCheck: identityCheck?.outcome, signatureCheck: signatureCheck?.outcome, artifactCheck: artifactCheck?.outcome, integrityPassed }, request.id);
      await client.query('COMMIT');
    } catch (error) {
      await client.query('ROLLBACK');
      throw error;
    } finally { client.release(); }
    return reply.code(passed ? 200 : 422).send({ runId: run.id, executionStatus: newStatus, findingStatus: 'unverified', checks, note: 'Run status and finding status remain separate; a passing test receipt does not itself confirm a vulnerability.' });
  });

  app.get('/v1/workflows/:id/gates', async (request, reply) => {
    if (!(await requireApi(request, reply))) return;
    const params = idParamsSchema.safeParse(request.params);
    if (!params.success) return reply.code(400).send({ error: 'invalid_id' });
    const workflow = await pool.query('SELECT id FROM workflows WHERE id=$1', [params.data.id]);
    if (!workflow.rows[0]) return reply.code(404).send({ error: 'workflow_not_found' });
    const result = await pool.query('SELECT gate_id, outcome, reasons, evidence_ids, evaluated_by, evaluated_at FROM readiness_gate_results WHERE workflow_id=$1 ORDER BY gate_id', [params.data.id]);
    const present = new Map(result.rows.map((row) => [String(row.gate_id), row]));
    const descriptions: Record<string, string> = {
      G1: 'Source authenticity and line provenance', G2: 'Independent RPC reproduction consistency', G3: 'Authorized scope and target identity',
      G4: 'Known-issue and overlap coverage', G5: 'Severity rubric and rationale', G6: 'Material claim provenance and receipt integrity',
      G7: 'Applicable symbolic analysis / counterexamples', G8: 'Positive, negative, and regression controls', G9: 'Independent adversarial review',
    };
    const gates = Object.entries(descriptions).map(([gateId, description]) => ({
      gateId, description, ...(present.has(gateId) ? present.get(gateId) : { outcome: 'inconclusive', reasons: ['No deterministic evaluation has been recorded.'], evidence_ids: [] }),
    }));
    const readyForSubmissionAuthorization = gates.every((gate) => gate.outcome === 'passed' || gate.outcome === 'not_applicable');
    return { workflowId: params.data.id, gates, readyForSubmissionAuthorization };
  });

  app.post('/v1/workflows/:id/review', async (request, reply) => {
    if (!layerEnabled('review')) return reply.code(503).send({ error: 'workflow_layer_disabled', layer: 'review' });
    if (!(await requireCredential(request, reply, 'approval'))) return;
    const actor = await requireActor(request, reply);
    if (!actor) return;
    const params = idParamsSchema.safeParse(request.params);
    const parsed = reviewSchema.safeParse(request.body);
    if (!params.success || !parsed.success) return reply.code(400).send({ error: 'invalid_review', issues: parsed.success ? [] : parsed.error.issues });
    const workflow = await pool.query('SELECT id, created_by, target_record_id, finding_status, execution_status, status FROM workflows WHERE id=$1', [params.data.id]);
    if (!workflow.rows[0]) return reply.code(404).send({ error: 'workflow_not_found' });
    if (!workflow.rows[0].target_record_id) return reply.code(403).send({ error: 'target_record_missing_on_workflow' });
    if (parsed.data.targetRecordId && parsed.data.targetRecordId !== String(workflow.rows[0].target_record_id)) return reply.code(409).send({ error: 'review_target_binding_mismatch' });
    const priorApprovals = await pool.query('SELECT approver_id FROM human_approvals WHERE workflow_id=$1', [params.data.id]);
    if (priorApprovals.rows.some((row) => String(row.approver_id) === actor)) return reply.code(403).send({ error: 'reviewer_cannot_be_approver', message: 'Independent review and run/submission approval must remain separate decisions.' });
    const reviewOracle = validateIndependentHumanReview(String(workflow.rows[0].created_by), actor, priorApprovals.rows.map((row) => String(row.approver_id)));
    if (reviewOracle.outcome !== 'allow') return reply.code(403).send({ error: 'independent_review_denied', oracle: reviewOracle });
    if (parsed.data.decision === 'accepted') {
      if (String(workflow.rows[0].status) !== 'independent_review') return reply.code(409).send({ error: 'workflow_not_in_independent_review', status: workflow.rows[0].status });
      try { assertTransition('independent_review', 'report_draft'); } catch { return reply.code(409).send({ error: 'invalid_workflow_transition' }); }
      if (String(workflow.rows[0].created_by) === actor) return reply.code(403).send({ error: 'independent_reviewer_required' });
      if (String(workflow.rows[0].finding_status) !== 'supported' || String(workflow.rows[0].execution_status) !== 'passed') return reply.code(409).send({ error: 'finding_or_execution_not_ready_for_review' });
      if (!parsed.data.evidenceIds.length) return reply.code(400).send({ error: 'review_evidence_required' });
      const evidence = await pool.query('SELECT id FROM evidence WHERE workflow_id=$1 AND target_record_id=$2 AND id=ANY($3::uuid[]) AND verified=true', [params.data.id, workflow.rows[0].target_record_id, parsed.data.evidenceIds]);
      if ((evidence.rowCount ?? 0) !== parsed.data.evidenceIds.length) return reply.code(409).send({ error: 'unverified_or_foreign_evidence' });
    }
    const reviewId = randomUUID();
    const client = await pool.connect();
    try {
      await client.query('BEGIN');
      await client.query('INSERT INTO review_decisions (id, workflow_id, target_record_id, decision, summary, evidence_ids, reviewer_id) VALUES ($1,$2,$3,$4,$5,$6,$7)',
        [reviewId, params.data.id, workflow.rows[0].target_record_id, parsed.data.decision, parsed.data.summary, parsed.data.evidenceIds, actor]);
      await client.query("UPDATE workflows SET review_status=$2, status=CASE WHEN $2='accepted' THEN 'report_draft' WHEN $2='rejected' THEN 'rejected' ELSE status END, updated_at=now() WHERE id=$1", [params.data.id, parsed.data.decision]);
      await writeGate(client, params.data.id, 'G9', parsed.data.decision === 'accepted' ? 'passed' : 'failed', parsed.data.decision === 'accepted' ? [] : [`Independent review decision: ${parsed.data.decision}`], actor, parsed.data.evidenceIds);
      await audit(client, actor, 'review.recorded', 'workflow', params.data.id, { reviewId, targetRecordId: workflow.rows[0].target_record_id, decision: parsed.data.decision, evidenceIds: parsed.data.evidenceIds }, request.id);
      await client.query('COMMIT');
    } catch (error) { await client.query('ROLLBACK'); throw error; }
    finally { client.release(); }
    return reply.code(201).send({ reviewId, decision: parsed.data.decision, gateG9: parsed.data.decision === 'accepted' ? 'passed' : 'failed' });
  });

  app.post('/v1/workflows/:id/finding-decision', async (request, reply) => {
    if (!(await requireCredential(request, reply, 'approval'))) return;
    const actor = await requireActor(request, reply);
    if (!actor) return;
    const params = idParamsSchema.safeParse(request.params);
    const parsed = gateDecisionSchema.safeParse(request.body);
    if (!params.success || !parsed.success) return reply.code(400).send({ error: 'invalid_finding_decision', issues: parsed.success ? [] : parsed.error.issues });
    const workflowResult = await pool.query('SELECT * FROM workflows WHERE id=$1', [params.data.id]);
    const workflow = workflowResult.rows[0];
    if (!workflow) return reply.code(404).send({ error: 'workflow_not_found' });
    if (!workflow.target_record_id) return reply.code(403).send({ error: 'target_record_missing_on_workflow' });
    const evidence = await pool.query('SELECT id, evidence_kind FROM evidence WHERE workflow_id=$1 AND target_record_id=$2 AND id=ANY($3::uuid[]) AND verified=true', [params.data.id, workflow.target_record_id, parsed.data.evidenceIds]);
    if ((evidence.rowCount ?? 0) !== parsed.data.evidenceIds.length) return reply.code(409).send({ error: 'unverified_or_foreign_evidence' });
    if (parsed.data.decision === 'supported') {
      if (String(workflow.status) !== 'evidence_review') return reply.code(409).send({ error: 'workflow_not_in_evidence_review', status: workflow.status });
      try { assertTransition('evidence_review', 'impact_review'); } catch { return reply.code(409).send({ error: 'invalid_workflow_transition' }); }
      if (String(workflow.execution_status) !== 'passed') return reply.code(409).send({ error: 'reproduction_not_passed' });
      if (!evidence.rows.some((row) => ['execution-output', 'trace', 'impact-measurement'].includes(String(row.evidence_kind)))) return reply.code(409).send({ error: 'execution_evidence_required' });
      const gates = await pool.query("SELECT gate_id, outcome FROM readiness_gate_results WHERE workflow_id=$1 AND gate_id IN ('G1','G2','G3','G4','G5','G6','G7','G8')", [params.data.id]);
      const byGate = new Map(gates.rows.map((row) => [String(row.gate_id), String(row.outcome)]));
      const missingGates = ['G1','G2','G3','G4','G5','G6','G7','G8'].filter((gateId) => !['passed','not_applicable'].includes(byGate.get(gateId) ?? 'inconclusive'));
      if (missingGates.length) return reply.code(409).send({ error: 'required_evidence_gates_not_passed', missingOrFailedGates: missingGates });
    }
    const client = await pool.connect();
    try {
      await client.query('BEGIN');
      await client.query("UPDATE workflows SET finding_status=$2, status=CASE WHEN $2='supported' THEN 'impact_review' ELSE status END, updated_at=now() WHERE id=$1", [params.data.id, parsed.data.decision]);
      await audit(client, actor, 'finding.decision_recorded', 'workflow', params.data.id, { targetRecordId: workflow.target_record_id, decision: parsed.data.decision, rationale: parsed.data.rationale, evidenceIds: parsed.data.evidenceIds }, request.id);
      await client.query('COMMIT');
    } catch (error) { await client.query('ROLLBACK'); throw error; }
    finally { client.release(); }
    return reply.code(200).send({ workflowId: params.data.id, findingStatus: parsed.data.decision, findingStatusIsSeparateFromExecution: true });
  });

  app.post('/v1/workflows/:id/report-draft', async (request, reply) => {
    if (!layerEnabled('reporting')) return reply.code(503).send({ error: 'workflow_layer_disabled', layer: 'reporting' });
    if (!(await requireCredential(request, reply, 'approval'))) return;
    const actor = await requireActor(request, reply);
    if (!actor) return;
    const params = idParamsSchema.safeParse(request.params);
    const parsed = reportDraftSchema.safeParse(request.body);
    if (!params.success || !parsed.success) return reply.code(400).send({ error: 'invalid_report_draft', issues: parsed.success ? [] : parsed.error.issues });
    const workflowResult = await pool.query('SELECT * FROM workflows WHERE id=$1', [params.data.id]);
    const workflow = workflowResult.rows[0];
    if (!workflow) return reply.code(404).send({ error: 'workflow_not_found' });
    if (!workflow.target_record_id) return reply.code(403).send({ error: 'target_record_missing_on_workflow' });
    if (parsed.data.targetRecordId && parsed.data.targetRecordId !== String(workflow.target_record_id)) return reply.code(409).send({ error: 'report_target_binding_mismatch' });
    if (String(workflow.status) !== 'report_draft' || String(workflow.finding_status) !== 'supported' || String(workflow.review_status) !== 'accepted' || String(workflow.execution_status) !== 'passed') return reply.code(409).send({ error: 'workflow_finding_review_or_execution_not_ready' });
    try { assertTransition('report_draft', 'human_approval'); } catch { return reply.code(409).send({ error: 'invalid_workflow_transition' }); }
    const ev = await pool.query('SELECT id, evidence_kind, claim, source_ref, metadata FROM evidence WHERE workflow_id=$1 AND target_record_id=$2 AND id=ANY($3::uuid[]) AND verified=true', [params.data.id, workflow.target_record_id, parsed.data.evidenceIds]);
    if ((ev.rowCount ?? 0) !== parsed.data.evidenceIds.length) return reply.code(409).send({ error: 'report_references_unverified_or_foreign_evidence' });
    const report = [
      `# ${parsed.data.title}`, '', `**Finding ID:** ${parsed.data.findingId}`, `**Workflow ID:** ${params.data.id}`, `**Pinned commit:** ${workflow.source_commit}`, `**Chain ID:** ${workflow.chain_id}`, `**Fork block:** ${workflow.fork_block}`, '',
      '## Summary', parsed.data.summary, '', '## Security impact', parsed.data.impact, '', '## Root cause', parsed.data.rootCause, '', '## Reproduction', parsed.data.reproduction, '', '## Evidence references',
      ...ev.rows.map((row) => `- ${row.id} (${row.evidence_kind}): ${row.claim}`), '', '## Limitations and assumptions', parsed.data.limitations, '',
      '> Draft generated inside Antigravity Security Mesh. Verify all claims and applicable Cantina rules before submission. No submission has been performed.', '',
    ].join('\n');
    const bytes = Buffer.from(report, 'utf8');
    const digest = sha256(bytes);
    const stored = await putArtifact(bytes, digest);
    const artifactId = randomUUID();
    const client = await pool.connect();
    try {
      await client.query('BEGIN');
      await client.query(
        `INSERT INTO artifact_manifests (id, workflow_id, target_record_id, name, media_type, storage_key, sha256, byte_length, provenance, created_by)
         VALUES ($1,$2,$3,$4,'text/markdown',$5,$6,$7,$8::jsonb,$9)
         ON CONFLICT (workflow_id, sha256) DO NOTHING`,
        [artifactId, params.data.id, workflow.target_record_id, `report-${parsed.data.findingId}.md`, stored.storageKey, stored.sha256, stored.byteLength, JSON.stringify({ evidenceIds: parsed.data.evidenceIds, generatedInsideMesh: true, targetRecordId: workflow.target_record_id }), actor],
      );
      const savedReport = await client.query('SELECT id FROM artifact_manifests WHERE workflow_id=$1 AND sha256=$2', [params.data.id, stored.sha256]);
      const finalArtifactId = String(savedReport.rows[0].id);
      await client.query("UPDATE workflows SET status='human_approval', submission_status='drafted', updated_at=now() WHERE id=$1", [params.data.id]);
      await client.query('INSERT INTO submission_records (id, workflow_id, target_record_id, finding_id, report_artifact_id, status, created_by) VALUES ($1,$2,$3,$4,$5,\'drafted\',$6)',
        [randomUUID(), params.data.id, workflow.target_record_id, parsed.data.findingId, finalArtifactId, actor]);
      await audit(client, actor, 'report.drafted', 'artifact', finalArtifactId, { workflowId: params.data.id, targetRecordId: workflow.target_record_id, findingId: parsed.data.findingId, sha256: stored.sha256 }, request.id);
      await client.query('COMMIT');
    } catch (error) { await client.query('ROLLBACK'); throw error; }
    finally { client.release(); }
    const saved = await pool.query('SELECT id FROM artifact_manifests WHERE workflow_id=$1 AND sha256=$2', [params.data.id, stored.sha256]);
    return reply.code(201).send({ artifactId: saved.rows[0]?.id ?? artifactId, sha256: stored.sha256, byteLength: stored.byteLength, status: 'drafted', submitted: false });
  });

  app.post('/v1/workflows/:id/approve-submission', async (request, reply) => {
    if (!(await requireCredential(request, reply, 'approval'))) return;
    const actor = await requireActor(request, reply);
    if (!actor) return;
    const params = idParamsSchema.safeParse(request.params);
    const parsed = approvalSubmissionSchema.safeParse(request.body);
    if (!params.success || !parsed.success) return reply.code(400).send({ error: 'invalid_submission_approval', issues: parsed.success ? [] : parsed.error.issues });
    const workflowResult = await pool.query('SELECT w.*, s.expires_at, s.disabled_at FROM workflows w JOIN authorized_scopes s ON s.id=w.scope_id WHERE w.id=$1', [params.data.id]);
    const workflow = workflowResult.rows[0];
    if (!workflow) return reply.code(404).send({ error: 'workflow_not_found' });
    if (workflow.disabled_at || new Date(String(workflow.expires_at)).getTime() <= Date.now()) return reply.code(403).send({ error: 'scope_expired_or_disabled' });
    if (!workflow.target_record_id) return reply.code(403).send({ error: 'target_record_missing_on_workflow' });
    if (parsed.data.targetRecordId && parsed.data.targetRecordId !== String(workflow.target_record_id)) return reply.code(409).send({ error: 'submission_target_binding_mismatch' });
    const reviewerResult = await pool.query('SELECT reviewer_id FROM review_decisions WHERE workflow_id=$1', [params.data.id]);
    if (reviewerResult.rows.some((row) => String(row.reviewer_id) === actor)) return reply.code(403).send({ error: 'submission_approver_cannot_be_reviewer', message: 'Review and submission approval must remain separate decisions by distinct human actors.' });
    if (String(workflow.created_by) === actor) return reply.code(403).send({ error: 'submission_approver_cannot_be_creator', message: 'Submission approval must be an independent human authorization.' });
    if (String(workflow.status) !== 'human_approval' || String(workflow.finding_status) !== 'supported' || String(workflow.review_status) !== 'accepted' || String(workflow.execution_status) !== 'passed') return reply.code(409).send({ error: 'workflow_finding_review_or_execution_not_ready' });
    const targetResult = await pool.query('SELECT t.*,s.program_slug FROM target_records t JOIN authorized_scopes s ON s.id=t.scope_id WHERE t.id=$1 AND t.scope_id=$2', [workflow.target_record_id, workflow.scope_id]);
    const scopeResult = await pool.query('SELECT * FROM authorized_scopes WHERE id=$1', [workflow.scope_id]);
    if (!targetResult.rows[0] || !scopeResult.rows[0]) return reply.code(403).send({ error: 'target_record_missing' });
    const targetDecision = validateTargetRecord(targetRecordFromDatabase(targetResult.rows[0] as Record<string, unknown>), scopeFromDatabase(scopeResult.rows[0] as Record<string, unknown>));
    if (targetDecision.outcome !== 'allow') return reply.code(403).send({ error: 'target_record_invalid', oracle: targetDecision });
    const artifact = await pool.query("SELECT id, name, target_record_id FROM artifact_manifests WHERE id=$1 AND workflow_id=$2 AND media_type='text/markdown'", [parsed.data.reportArtifactId, params.data.id]);
    if (!artifact.rows[0] || !String(artifact.rows[0].name).startsWith(`report-${parsed.data.findingId}.`)) return reply.code(409).send({ error: 'report_artifact_not_found' });
    const artifactBinding = bindEvidenceToTarget(String(workflow.target_record_id), artifact.rows[0].target_record_id ? String(artifact.rows[0].target_record_id) : null);
    if (artifactBinding.outcome !== 'allow') return reply.code(409).send({ error: 'report_target_binding_mismatch', oracle: artifactBinding });
    const acceptedReview = await pool.query("SELECT reviewer_id FROM review_decisions WHERE workflow_id=$1 AND target_record_id=$2 AND decision='accepted' ORDER BY created_at DESC LIMIT 1", [params.data.id, workflow.target_record_id]);
    const approvalSeparation = validateSeparateSubmissionApproval(String(acceptedReview.rows[0]?.reviewer_id ?? ''), actor, String(workflow.created_by));
    if (approvalSeparation.outcome !== 'allow') return reply.code(403).send({ error: 'separate_submission_approver_required', oracle: approvalSeparation });
    const gatesResult = await pool.query("SELECT gate_id, outcome FROM readiness_gate_results WHERE workflow_id=$1 AND gate_id <> 'G9'", [params.data.id]);
    const gateMap = new Map(gatesResult.rows.map((row) => [String(row.gate_id), String(row.outcome)]));
    const required = ['G1','G2','G3','G4','G5','G6','G7','G8'];
    const missing = required.filter((gateId) => !['passed', 'not_applicable'].includes(gateMap.get(gateId) ?? 'inconclusive'));
    const g9 = await pool.query("SELECT outcome FROM readiness_gate_results WHERE workflow_id=$1 AND gate_id='G9'", [params.data.id]);
    if (missing.length || String(g9.rows[0]?.outcome) !== 'passed') return reply.code(409).send({ error: 'readiness_gates_incomplete', missingOrFailedGates: [...missing, ...(String(g9.rows[0]?.outcome) === 'passed' ? [] : ['G9'])] });
    const approvalId = randomUUID();
    const client = await pool.connect();
    try {
      await client.query('BEGIN');
      await client.query("INSERT INTO human_approvals (id, workflow_id, target_record_id, approval_type, decision, rationale, artifact_id, approver_id) VALUES ($1,$2,$3,'submission','approved',$4,$5,$6)",
        [approvalId, params.data.id, workflow.target_record_id, parsed.data.rationale, parsed.data.reportArtifactId, actor]);
      await client.query("UPDATE workflows SET approval_status='approved', updated_at=now() WHERE id=$1", [params.data.id]);
      await client.query("UPDATE submission_records SET status='approved', authorization_id=$2 WHERE workflow_id=$1 AND report_artifact_id=$3 AND status='drafted' AND target_record_id=$4",
        [params.data.id, approvalId, parsed.data.reportArtifactId, workflow.target_record_id]);
      await audit(client, actor, 'submission.approved', 'workflow', params.data.id, { approvalId, targetRecordId: workflow.target_record_id, reportArtifactId: parsed.data.reportArtifactId, externalSubmissionPerformed: false }, request.id);
      await client.query('COMMIT');
    } catch (error) { await client.query('ROLLBACK'); throw error; }
    finally { client.release(); }
    return reply.code(200).send({ workflowId: params.data.id, approvalId, approvalStatus: 'approved', submissionStatus: 'drafted', externalSubmissionPerformed: false, message: 'Human authorization recorded. No Cantina submission connector is configured.' });
  });

  app.addHook('onClose', async () => { /* pool is closed by process shutdown handler, not per app instance */ });
  return app;
}

export async function startServer(): Promise<void> {
  const issues = validateAgentRegistry();
  if (issues.length) throw new Error(`Agent registry invalid: ${issues.join('; ')}`);
  await bootstrapRegistry();
  const app = await createServer();
  await app.listen({ host: config.HOST, port: config.PORT });
  const workerController = new AbortController();
  const workerId = `mesh-worker-${process.pid}`;
  const workerPromise = runWorkerLoop(workerId, BUILTIN_HANDLERS, workerController.signal);
  app.log.info({ port: config.PORT, registeredAgents: AGENT_REGISTRY.length, suiteCount: Object.keys(SUITES).length }, 'Antigravity Security Mesh API listening');

  const shutdown = async (signal: string) => {
    app.log.info({ signal }, 'shutting down');
    workerController.abort();
    await app.close();
    await workerPromise;
    await pool.end();
    process.exit(0);
  };
  process.once('SIGINT', () => { void shutdown('SIGINT'); });
  process.once('SIGTERM', () => { void shutdown('SIGTERM'); });
}
