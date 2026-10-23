import { createHash, randomUUID } from 'node:crypto';
import type { PoolClient } from 'pg';
import { pool } from '../db/pool.js';
import { scopeFromDatabase, targetRecordFromDatabase, validateTargetRecord } from '../oracles/target-record.js';

export interface NewAgentTask {
  workflowId: string;
  targetRecordId?: string;
  agentId: string;
  idempotencyKey: string;
  contractVersion: string;
  input: Record<string, unknown>;
  dependencyTaskIds?: string[];
  maxAttempts?: number;
}

export interface LeasedAgentTask {
  id: string;
  workflow_id: string;
  target_record_id: string;
  workflowId: string;
  agent_id: string;
  input: Record<string, unknown>;
  attempt: number;
  max_attempts: number;
  contract_version: string;
  max_runtime_seconds: number;
  lease_token: string;
  lease_expires_at: string;
}

async function inTransaction<T>(run: (client: PoolClient) => Promise<T>): Promise<T> {
  const client = await pool.connect();
  try {
    await client.query('BEGIN');
    const result = await run(client);
    await client.query('COMMIT');
    return result;
  } catch (error) {
    await client.query('ROLLBACK');
    throw error;
  } finally {
    client.release();
  }
}

function stable(value: unknown): string {
  if (value === null || typeof value !== 'object') return JSON.stringify(value) ?? 'null';
  if (Array.isArray(value)) return `[${value.map(stable).join(',')}]`;
  const record = value as Record<string, unknown>;
  return `{${Object.keys(record).sort().map((key) => `${JSON.stringify(key)}:${stable(record[key])}`).join(',')}}`;
}

/** Creates an idempotent task record. This never starts a worker or executes a tool. */
export async function enqueueAgentTask(task: NewAgentTask): Promise<{ id: string; created: boolean }> {
  const dependencies = [...new Set(task.dependencyTaskIds ?? [])];
  if (!task.idempotencyKey.trim() || !task.contractVersion.trim()) throw new Error('Task idempotency key and contract version are required.');
  if ((task.maxAttempts ?? 2) < 1 || (task.maxAttempts ?? 2) > 20) throw new Error('maxAttempts must be between 1 and 20.');
  const requestSha256 = createHash('sha256').update(stable({ agentId: task.agentId, contractVersion: task.contractVersion, input: task.input, dependencies: dependencies.sort(), maxAttempts: task.maxAttempts ?? 2 })).digest('hex');

  return inTransaction(async (client) => {
    const eligibility = await client.query(
      `SELECT w.status, w.target_record_id, s.disabled_at, s.expires_at, a.enabled, a.profile->>'approvalRequired' AS approval_required,
              t.*, s.program_slug AS current_program_slug
       FROM workflows w
       JOIN authorized_scopes s ON s.id=w.scope_id
       JOIN target_records t ON t.id=w.target_record_id AND t.scope_id=w.scope_id
       JOIN agent_profiles a ON a.agent_id=$2
       WHERE w.id=$1 FOR SHARE OF w, s, a`,
      [task.workflowId, task.agentId],
    );
    const row = eligibility.rows[0];
    if (!row) throw new Error('Workflow, scope, or registered agent does not exist.');
    if (!row.enabled) throw new Error('Agent profile is disabled.');
    if (row.approval_required !== 'false') throw new Error('This agent requires a separate approved execution path and cannot use the analysis queue.');
    if (row.disabled_at || new Date(String(row.expires_at)).getTime() <= Date.now()) throw new Error('Workflow scope is expired or disabled.');
    if (task.targetRecordId && task.targetRecordId !== String(row.target_record_id)) throw new Error('Task target record does not match its workflow.');
    const target = targetRecordFromDatabase({ ...row, program_slug: row.current_program_slug });
    const scopeResult = await client.query('SELECT * FROM authorized_scopes WHERE id=(SELECT scope_id FROM workflows WHERE id=$1)', [task.workflowId]);
    const targetDecision = validateTargetRecord(target, scopeFromDatabase(scopeResult.rows[0] as Record<string, unknown>));
    if (targetDecision.outcome !== 'allow') throw new Error(`Target dispatch denied: ${targetDecision.reasons.join(' ')}`);
    if (String(row.status) !== 'analysis') throw new Error('Agent analysis tasks can be queued only after the workflow reaches analysis.');

    const inserted = await client.query(
      `INSERT INTO agent_tasks (id, workflow_id, target_record_id, agent_id, status, input, attempt, idempotency_key, request_sha256, contract_version, max_attempts)
       VALUES ($1,$2,$9,$3,'queued',$4::jsonb,0,$5,$6,$7,$8)
       ON CONFLICT (workflow_id, idempotency_key) WHERE idempotency_key IS NOT NULL DO NOTHING
       RETURNING id`,
      [randomUUID(), task.workflowId, task.agentId, JSON.stringify(task.input), task.idempotencyKey, requestSha256, task.contractVersion, task.maxAttempts ?? 2, row.target_record_id],
    );
    let taskId = inserted.rows[0]?.id as string | undefined;
    const created = Boolean(taskId);
    if (!taskId) {
      const existing = await client.query('SELECT id, request_sha256 FROM agent_tasks WHERE workflow_id=$1 AND idempotency_key=$2 FOR UPDATE', [task.workflowId, task.idempotencyKey]);
      taskId = existing.rows[0]?.id as string | undefined;
      if (!taskId) throw new Error('Idempotent task insert could not be reconciled.');
      if (String(existing.rows[0]?.request_sha256) !== requestSha256) throw new Error('Idempotency key was already used with a different task contract or input.');
    }

    for (const dependencyId of dependencies) {
      const dependency = await client.query('SELECT workflow_id FROM agent_tasks WHERE id=$1 FOR SHARE', [dependencyId]);
      if (!dependency.rows[0] || String(dependency.rows[0].workflow_id) !== task.workflowId) throw new Error('Task dependencies must exist in the same workflow.');
      await client.query('INSERT INTO agent_task_dependencies (task_id, depends_on_task_id) VALUES ($1,$2) ON CONFLICT DO NOTHING', [taskId, dependencyId]);
    }
    return { id: taskId, created };
  });
}

/** Claims one eligible task atomically across competing workers using SKIP LOCKED. */
export async function claimAgentTask(workerId: string, leaseSeconds = 120): Promise<LeasedAgentTask | undefined> {
  if (!/^[a-zA-Z0-9][a-zA-Z0-9._:-]{2,127}$/.test(workerId)) throw new Error('Invalid worker ID.');
  if (!Number.isInteger(leaseSeconds) || leaseSeconds < 10 || leaseSeconds > 3600) throw new Error('Lease must be between 10 and 3600 seconds.');
  return inTransaction(async (client) => {
    const token = randomUUID();
    const result = await client.query(
      `WITH candidate AS (
         SELECT t.id, t.contract_version, t.target_record_id, (a.profile->>'maxRuntimeSeconds')::integer AS max_runtime_seconds FROM agent_tasks t
         JOIN agent_profiles a ON a.agent_id=t.agent_id AND a.enabled=true
         JOIN workflows w ON w.id=t.workflow_id AND w.status='analysis'
         JOIN authorized_scopes s ON s.id=w.scope_id AND s.disabled_at IS NULL AND s.expires_at > now()
         JOIN target_records tr ON tr.id=w.target_record_id AND tr.id=t.target_record_id AND tr.status='active' AND tr.expires_at > now()
         WHERE t.status='queued' AND t.available_at <= now() AND t.attempt < t.max_attempts
           AND a.profile->>'approvalRequired'='false'
           AND NOT EXISTS (
             SELECT 1 FROM agent_task_dependencies d JOIN agent_tasks p ON p.id=d.depends_on_task_id
             WHERE d.task_id=t.id AND p.status <> 'passed'
           )
         ORDER BY t.created_at, t.id LIMIT 1
         FOR UPDATE OF t SKIP LOCKED
       )
       UPDATE agent_tasks t SET status='running', attempt=t.attempt+1, lease_owner=$1, lease_token=$2,
         lease_expires_at=now() + ($3::integer * interval '1 second'), updated_at=now()
       FROM candidate c WHERE t.id=c.id
         RETURNING t.id, t.workflow_id, t.target_record_id, t.agent_id, t.input, t.attempt, t.max_attempts, t.lease_token, t.lease_expires_at, c.contract_version, c.max_runtime_seconds`,
      [workerId, token, leaseSeconds],
    );
    const row = result.rows[0];
    if (!row) return undefined;
    const binding = await client.query(`SELECT t.*,s.program_slug,s.id AS loaded_scope_id,s.repository_url AS scope_repository_url,s.source_commit AS scope_source_commit,s.chain_id AS scope_chain_id,s.target_addresses AS scope_target_addresses,s.required_fork_block,s.allowed_methods AS scope_allowed_methods,s.program_authorization_ref,s.restrictions,s.expires_at AS scope_expires_at,s.disabled_at
      FROM target_records t JOIN authorized_scopes s ON s.id=t.scope_id WHERE t.id=$1 AND t.scope_id=(SELECT scope_id FROM workflows WHERE id=$2)`, [row.target_record_id, row.workflow_id]);
    let denyReason = 'Target record or authorized scope could not be reloaded at claim time.';
    if (binding.rows[0]) {
      const item = binding.rows[0] as Record<string, unknown>;
      const scope = scopeFromDatabase({ id: item.loaded_scope_id, program_slug: item.program_slug, repository_url: item.scope_repository_url, source_commit: item.scope_source_commit, chain_id: item.scope_chain_id, target_addresses: item.scope_target_addresses, required_fork_block: item.required_fork_block, allowed_methods: item.scope_allowed_methods, program_authorization_ref: item.program_authorization_ref, restrictions: item.restrictions, expires_at: item.scope_expires_at, disabled_at: item.disabled_at });
      const decision = validateTargetRecord(targetRecordFromDatabase({ ...item, program_slug: item.program_slug }), scope);
      if (decision.outcome === 'allow') return { ...row, id: String(row.id), workflowId: String(row.workflow_id), target_record_id: String(row.target_record_id), agent_id: String(row.agent_id), input: row.input as Record<string, unknown>, attempt: Number(row.attempt), max_attempts: Number(row.max_attempts), contract_version: String(row.contract_version), max_runtime_seconds: Number(row.max_runtime_seconds) || 120, lease_token: String(row.lease_token), lease_expires_at: new Date(String(row.lease_expires_at)).toISOString() };
      denyReason = decision.reasons.join(' ');
    }
    await client.query(`UPDATE agent_tasks SET status='failed',last_error=$2,error_summary=$2,lease_owner=NULL,lease_token=NULL,lease_expires_at=NULL,updated_at=now() WHERE id=$1`, [row.id, `Oracle claim denied: ${denyReason}`]);
    return undefined;
  });
}

export async function renewAgentTaskLease(taskId: string, workerId: string, token: string, leaseSeconds = 120): Promise<boolean> {
  if (!Number.isInteger(leaseSeconds) || leaseSeconds < 10 || leaseSeconds > 3600) throw new Error('Lease must be between 10 and 3600 seconds.');
  const result = await pool.query(
    `UPDATE agent_tasks task SET lease_expires_at=now() + ($4::integer * interval '1 second'), updated_at=now()
     FROM workflows w
     JOIN authorized_scopes s ON s.id=w.scope_id
     JOIN target_records tr ON tr.id=w.target_record_id
     CROSS JOIN agent_profiles a
     WHERE task.id=$1 AND task.workflow_id=w.id AND task.target_record_id=tr.id AND a.agent_id=task.agent_id
       AND task.lease_owner=$2 AND task.lease_token=$3 AND task.status='running' AND task.lease_expires_at > now()
       AND w.status='analysis' AND s.disabled_at IS NULL AND s.expires_at > now()
       AND tr.status='active' AND tr.expires_at > now() AND a.enabled=true
       AND a.profile->>'approvalRequired'='false'`,
    [taskId, workerId, token, leaseSeconds],
  );
  return result.rowCount === 1;
}

export async function completeAgentTask(taskId: string, workerId: string, token: string, output: Record<string, unknown>): Promise<boolean> {
  const result = await pool.query(
    `UPDATE agent_tasks task SET status='passed', output=$4::jsonb, lease_owner=NULL, lease_token=NULL, lease_expires_at=NULL, updated_at=now()
     FROM workflows w
     JOIN authorized_scopes s ON s.id=w.scope_id
     JOIN target_records tr ON tr.id=w.target_record_id
     CROSS JOIN agent_profiles a
     WHERE task.id=$1 AND task.workflow_id=w.id AND task.target_record_id=tr.id AND a.agent_id=task.agent_id
       AND task.lease_owner=$2 AND task.lease_token=$3 AND task.status='running' AND task.lease_expires_at > now()
       AND w.status='analysis' AND s.disabled_at IS NULL AND s.expires_at > now()
       AND tr.status='active' AND tr.expires_at > now() AND a.enabled=true
       AND a.profile->>'approvalRequired'='false'`,
    [taskId, workerId, token, JSON.stringify(output)],
  );
  return result.rowCount === 1;
}

export async function failAgentTask(taskId: string, workerId: string, token: string, reason: string, retryDelaySeconds = 5): Promise<'retry_queued' | 'failed' | 'lease_lost'> {
  return inTransaction(async (client) => {
    const result = await client.query(
      `UPDATE agent_tasks SET status=CASE WHEN attempt < max_attempts THEN 'queued' ELSE 'failed' END,
         available_at=now() + ($4::integer * interval '1 second'), error_summary=left($5,2000), last_error=left($5,2000),
         lease_owner=NULL, lease_token=NULL, lease_expires_at=NULL, updated_at=now()
       WHERE id=$1 AND lease_owner=$2 AND lease_token=$3 AND status='running' AND lease_expires_at > now()
       RETURNING status`,
      [taskId, workerId, token, Math.max(0, Math.min(retryDelaySeconds, 3600)), reason],
    );
    const status = result.rows[0]?.status;
    if (!status) return 'lease_lost';
    return status === 'queued' ? 'retry_queued' : 'failed';
  });
}

/** Reclaims expired leases and terminalizes queued tasks that can no longer make progress. */
export async function expireAgentTaskLeases(): Promise<{ requeued: number; failed: number }> {
  return inTransaction(async (client) => {
    const expired = await client.query(
      `UPDATE agent_tasks SET status=CASE WHEN attempt < max_attempts THEN 'queued' ELSE 'failed' END,
         available_at=now(), last_error='Worker lease expired.', error_summary='Worker lease expired.',
         lease_owner=NULL, lease_token=NULL, lease_expires_at=NULL, updated_at=now()
       WHERE status='running' AND lease_expires_at <= now() RETURNING status`,
    );

    const ineligible = await client.query(
      `UPDATE agent_tasks task
       SET status='failed', last_error='Task is no longer eligible: workflow, scope, target, or agent is inactive.',
           error_summary='Task is no longer eligible: workflow, scope, target, or agent is inactive.',
           lease_owner=NULL, lease_token=NULL, lease_expires_at=NULL, updated_at=now()
       WHERE task.status IN ('queued','running') AND NOT EXISTS (
         SELECT 1 FROM workflows w
         JOIN authorized_scopes s ON s.id=w.scope_id
         JOIN target_records tr ON tr.id=w.target_record_id
         JOIN agent_profiles a ON a.agent_id=task.agent_id
         WHERE w.id=task.workflow_id AND tr.id=task.target_record_id
           AND w.status='analysis' AND s.disabled_at IS NULL AND s.expires_at > now()
           AND tr.status='active' AND tr.expires_at > now() AND a.enabled=true
           AND a.profile->>'approvalRequired'='false'
       ) RETURNING task.id`,
    );

    const blocked = await client.query(
      `WITH RECURSIVE blocked(id) AS (
         SELECT task.id FROM agent_tasks task
         WHERE task.status='queued' AND EXISTS (
           SELECT 1 FROM agent_task_dependencies d
           JOIN agent_tasks dependency ON dependency.id=d.depends_on_task_id
           WHERE d.task_id=task.id AND dependency.status IN ('failed','timed_out','cancelled','inconclusive')
         )
         UNION
         SELECT child.id FROM agent_tasks child
         JOIN agent_task_dependencies d ON d.task_id=child.id
         JOIN blocked parent ON parent.id=d.depends_on_task_id
         WHERE child.status='queued'
       )
       UPDATE agent_tasks task
       SET status='failed', last_error='Task prerequisite failed; dependent work was cancelled.',
           error_summary='Task prerequisite failed; dependent work was cancelled.', updated_at=now()
       FROM blocked WHERE task.id=blocked.id AND task.status='queued' RETURNING task.id`,
    );

    const requeued = expired.rows.filter((row) => row.status === 'queued').length;
    const failedLeases = expired.rows.filter((row) => row.status === 'failed').length;
    return { requeued, failed: failedLeases + ineligible.rows.length + blocked.rows.length };
  });
}
