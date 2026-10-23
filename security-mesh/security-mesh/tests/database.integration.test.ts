import { randomBytes, randomUUID, generateKeyPairSync } from 'node:crypto';
import { afterAll, beforeAll, describe, expect, it } from 'vitest';

const dbUrl = process.env.TEST_DATABASE_URL;
const dbDescribe = dbUrl ? describe : describe.skip;

dbDescribe('PostgreSQL target, runner lease, and audit integration', () => {
  const apiToken = randomBytes(32).toString('base64url');
  const adminToken = randomBytes(32).toString('base64url');
  const approvalToken = randomBytes(32).toString('base64url');
  const runnerToken = randomBytes(32).toString('base64url');
  const runnerId = `runner-test-${randomBytes(4).toString('hex')}`;

  let app: Awaited<ReturnType<(typeof import('../src/server.js'))['createServer']>> | undefined;
  let databasePool: (typeof import('../src/db/pool.js'))['pool'] | undefined;
  let ed25519PublicKeyPem: string;
  let ed25519PrivateKeyPem: string;

  beforeAll(async () => {
    if (!dbUrl) throw new Error('TEST_DATABASE_URL is required.');
    process.env.NODE_ENV = 'test';
    process.env.DATABASE_URL = dbUrl;
    process.env.API_TOKEN = apiToken;
    process.env.ADMIN_API_TOKEN = adminToken;
    process.env.HUMAN_APPROVAL_TOKEN = approvalToken;
    process.env.RUNNER_TOKEN = runnerToken;
    process.env.RUNNER_ID = runnerId;

    const keypair = generateKeyPairSync('ed25519');
    ed25519PublicKeyPem = keypair.publicKey.export({ type: 'spki', format: 'pem' }).toString();
    ed25519PrivateKeyPem = keypair.privateKey.export({ type: 'pkcs8', format: 'pem' }).toString();

    const serverModule = await import('../src/server.js');
    databasePool = (await import('../src/db/pool.js')).pool;
    app = await serverModule.createServer();
    await app.ready();
  });

  afterAll(async () => {
    await app?.close();
    await databasePool?.end();
  });

  it('verifies migration ledger table _migrations exists and has entries', async () => {
    const result = await databasePool!.query('SELECT id, checksum, applied_at FROM _migrations ORDER BY id');
    expect(result.rows.length).toBeGreaterThanOrEqual(1);
    expect(result.rows[0]).toHaveProperty('checksum');
  });

  it('creates exact target-bound work, denies out-of-scope targets, and verifies audit chain', async () => {
    const sourceCommit = 'a'.repeat(40);
    const programSlug = `local-integration-${randomBytes(4).toString('hex')}`;
    const targetAddress = '0x1111111111111111111111111111111111111111';
    const scopeExpiresAt = new Date(Date.now() + 30 * 60_000).toISOString();
    const targetExpiresAt = new Date(Date.now() + 29 * 60_000).toISOString();

    // 1. Register valid scope
    const scopeResponse = await app!.inject({
      method: 'POST',
      url: '/v1/scopes',
      headers: { 'x-admin-token': adminToken, 'x-actor-id': 'integration-admin' },
      payload: {
        programSlug,
        repositoryUrl: 'https://github.com/example/cantina-fixture',
        sourceCommit,
        chainId: 31337,
        targetAddresses: [targetAddress],
        requiredForkBlock: 100,
        allowedMethods: ['local-test'],
        programAuthorizationRef: 'Synthetic local database integration fixture only',
        expiresAt: scopeExpiresAt,
        restrictions: {},
      },
    });
    expect(scopeResponse.statusCode).toBe(201);
    const scopeId = scopeResponse.json<{ id: string }>().id;

    // 2. Create matching target record
    const targetResponse = await app!.inject({
      method: 'POST',
      url: '/v1/target-records',
      headers: { 'x-admin-token': adminToken, 'x-actor-id': 'integration-admin' },
      payload: {
        scopeId,
        targetId: 'integration-fixture',
        targetAddress,
        repositoryUrl: 'https://github.com/example/cantina-fixture',
        sourceCommit,
        chainId: 31337,
        forkBlock: 100,
        environment: 'local-test',
        allowedMethods: ['local-test'],
        suiteIds: ['build'],
        expiresAt: targetExpiresAt,
      },
    });
    expect(targetResponse.statusCode, targetResponse.body).toBe(201);
    const targetRecordId = targetResponse.json<{ id: string }>().id;

    // 3. Check target record
    const targetCheck = await app!.inject({
      method: 'GET',
      url: `/v1/target-records/${targetRecordId}/check`,
      headers: { authorization: `Bearer ${apiToken}` },
    });
    expect(targetCheck.statusCode).toBe(200);
    expect(targetCheck.json<{ valid: boolean }>().valid).toBe(true);

    // 4. Negative test: Deny out-of-scope address
    const blockedTarget = await app!.inject({
      method: 'POST',
      url: '/v1/target-records',
      headers: { 'x-admin-token': adminToken, 'x-actor-id': 'integration-admin' },
      payload: {
        scopeId,
        targetId: 'outside-target',
        targetAddress: '0x2222222222222222222222222222222222222222',
        repositoryUrl: 'https://github.com/example/cantina-fixture',
        sourceCommit,
        chainId: 31337,
        forkBlock: 100,
        environment: 'local-test',
        allowedMethods: ['local-test'],
        suiteIds: ['build'],
        expiresAt: targetExpiresAt,
      },
    });
    expect(blockedTarget.statusCode).toBe(403);

    // 5. Negative test: Deny expired scope / target record
    const expiredTarget = await app!.inject({
      method: 'POST',
      url: '/v1/target-records',
      headers: { 'x-admin-token': adminToken, 'x-actor-id': 'integration-admin' },
      payload: {
        scopeId,
        targetId: 'expired-target',
        targetAddress,
        repositoryUrl: 'https://github.com/example/cantina-fixture',
        sourceCommit,
        chainId: 31337,
        forkBlock: 100,
        environment: 'local-test',
        allowedMethods: ['local-test'],
        suiteIds: ['build'],
        expiresAt: new Date(Date.now() - 60_000).toISOString(), // expired
      },
    });
    expect(expiredTarget.statusCode).toBe(400);

    // 6. Create workflow bound to target record
    const workflow = await app!.inject({
      method: 'POST',
      url: '/v1/workflows',
      headers: { authorization: `Bearer ${apiToken}`, 'x-actor-id': 'integration-researcher' },
      payload: {
        targetRecordId,
        programSlug,
        repositoryUrl: 'https://github.com/example/cantina-fixture',
        sourceCommit,
        chainId: 31337,
        targetAddresses: [targetAddress],
        forkBlock: 100,
        requestedMethods: ['local-test'],
        findingId: 'synthetic-integration',
        title: 'Local integration fixture',
      },
    });
    expect(workflow.statusCode).toBe(201);
    const workflowId = workflow.json<{ id: string }>().id;

    // 6a. Exercise queue dependency failure and target-revocation recovery.
    await databasePool!.query("UPDATE workflows SET status='analysis' WHERE id=$1", [workflowId]);
    const { renewAgentTaskLease, completeAgentTask, expireAgentTaskLeases } = await import('../src/orchestration/task-queue.js');
    const parentTaskId = randomUUID();
    const childTaskId = randomUUID();
    await databasePool!.query(
      `INSERT INTO agent_tasks (id,workflow_id,target_record_id,agent_id,status,input,attempt,idempotency_key,request_sha256,contract_version,max_attempts)
       VALUES ($1,$2,$3,'bounty-scanner','failed','{}'::jsonb,1,$4,$5,'1.0.0',2),
              ($6,$2,$3,'bounty-scanner','queued','{}'::jsonb,0,$7,$8,'1.0.0',2)`,
      [parentTaskId, workflowId, targetRecordId, `parent-${randomUUID()}`, 'a'.repeat(64), childTaskId, `child-${randomUUID()}`, 'b'.repeat(64)],
    );
    await databasePool!.query('INSERT INTO agent_task_dependencies (task_id,depends_on_task_id) VALUES ($1,$2)', [childTaskId, parentTaskId]);
    await expireAgentTaskLeases();
    const childStatus = await databasePool!.query('SELECT status FROM agent_tasks WHERE id=$1', [childTaskId]);
    expect(childStatus.rows[0]?.status).toBe('failed');

    const runningTaskId = randomUUID();
    const leaseToken = randomUUID();
    await databasePool!.query(
      `INSERT INTO agent_tasks (id,workflow_id,target_record_id,agent_id,status,input,attempt,idempotency_key,request_sha256,contract_version,max_attempts,lease_owner,lease_token,lease_expires_at)
       VALUES ($1,$2,$3,'bounty-scanner','running','{}'::jsonb,1,$4,$5,'1.0.0',2,'integration-worker-1',$6,now()+interval '60 seconds')`,
      [runningTaskId, workflowId, targetRecordId, `running-${randomUUID()}`, 'c'.repeat(64), leaseToken],
    );

    // 7. Verify audit chain integrity
    const audit = await app!.inject({
      method: 'GET',
      url: '/v1/audit/verify',
      headers: { authorization: `Bearer ${apiToken}` },
    });
    expect(audit.statusCode).toBe(200);
    expect(audit.json<{ valid: boolean; entriesChecked: number }>().valid).toBe(true);
    expect(audit.json<{ entriesChecked: number }>().entriesChecked).toBeGreaterThanOrEqual(2);

    // 8. Negative test: prevent audit mutation (UPDATE)
    await expect(
      databasePool!.query('UPDATE execution_audit SET action=action WHERE chain_position=1')
    ).rejects.toThrow(/append-only/i);

    // 9. Negative test: prevent audit mutation (DELETE)
    await expect(
      databasePool!.query('DELETE FROM execution_audit WHERE chain_position=1')
    ).rejects.toThrow(/append-only/i);

    // 10. Revoke target record and confirm subsequent workflows blocked
    const revokeResponse = await app!.inject({
      method: 'POST',
      url: `/v1/target-records/${targetRecordId}/revoke`,
      headers: { 'x-admin-token': adminToken, 'x-actor-id': 'integration-admin' },
    });
    expect(revokeResponse.statusCode).toBe(200);
    expect(revokeResponse.json<{ status: string }>().status).toBe('revoked');

    expect(await renewAgentTaskLease(runningTaskId, 'integration-worker-1', leaseToken)).toBe(false);
    expect(await completeAgentTask(runningTaskId, 'integration-worker-1', leaseToken, { ok: true })).toBe(false);
    const queuedTaskId = randomUUID();
    await databasePool!.query(
      `INSERT INTO agent_tasks (id,workflow_id,target_record_id,agent_id,status,input,attempt,idempotency_key,request_sha256,contract_version,max_attempts)
       VALUES ($1,$2,$3,'bounty-scanner','queued','{}'::jsonb,0,$4,$5,'1.0.0',2)`,
      [queuedTaskId, workflowId, targetRecordId, `queued-${randomUUID()}`, 'd'.repeat(64)],
    );
    await expireAgentTaskLeases();
    const recovered = await databasePool!.query('SELECT id,status FROM agent_tasks WHERE id=ANY($1::uuid[])', [[runningTaskId, queuedTaskId]]);
    expect(recovered.rows).toHaveLength(2);
    expect(recovered.rows.every((row) => row.status === 'failed')).toBe(true);

    const blockedAfterRevocation = await app!.inject({
      method: 'POST',
      url: '/v1/workflows',
      headers: { authorization: `Bearer ${apiToken}`, 'x-actor-id': 'integration-researcher' },
      payload: {
        targetRecordId,
        programSlug,
        repositoryUrl: 'https://github.com/example/cantina-fixture',
        sourceCommit,
        chainId: 31337,
        targetAddresses: [targetAddress],
        forkBlock: 100,
        requestedMethods: ['local-test'],
        findingId: 'synthetic-integration-blocked',
        title: 'Blocked after revocation',
      },
    });
    expect(blockedAfterRevocation.statusCode).toBe(403);
  });

  it('registers runner, approves fixed run, claims lease, and rejects forged receipts', async () => {
    const sourceCommit = 'b'.repeat(40);
    const programSlug = `runner-integration-${randomBytes(4).toString('hex')}`;
    const targetAddress = '0x3333333333333333333333333333333333333333';
    const expiresAt = new Date(Date.now() + 30 * 60_000).toISOString();

    // Register scope & target record
    const scopeRes = await app!.inject({
      method: 'POST',
      url: '/v1/scopes',
      headers: { 'x-admin-token': adminToken, 'x-actor-id': 'integration-admin' },
      payload: {
        programSlug,
        repositoryUrl: 'https://github.com/example/runner-target',
        sourceCommit,
        chainId: 31337,
        targetAddresses: [targetAddress],
        requiredForkBlock: 200,
        allowedMethods: ['local-test'],
        programAuthorizationRef: 'Runner integration test',
        expiresAt,
        restrictions: {},
      },
    });
    const scopeId = scopeRes.json<{ id: string }>().id;

    const targetRes = await app!.inject({
      method: 'POST',
      url: '/v1/target-records',
      headers: { 'x-admin-token': adminToken, 'x-actor-id': 'integration-admin' },
      payload: {
        scopeId,
        targetId: 'runner-target',
        targetAddress,
        repositoryUrl: 'https://github.com/example/runner-target',
        sourceCommit,
        chainId: 31337,
        forkBlock: 200,
        environment: 'local-test',
        allowedMethods: ['local-test'],
        suiteIds: ['build'],
        expiresAt,
      },
    });
    const targetRecordId = targetRes.json<{ id: string }>().id;

    // Register runner with Ed25519 key
    const runnerReg = await app!.inject({
      method: 'POST',
      url: '/v1/runners/register',
      headers: { 'x-admin-token': adminToken, 'x-actor-id': 'integration-admin' },
      payload: {
        runnerId,
        publicKeyPem: ed25519PublicKeyPem,
        allowedSuites: ['build'],
      },
    });
    expect(runnerReg.statusCode).toBe(201);
    const issuedRunnerToken = runnerReg.json<{ token: string }>().token;

    // Create workflow
    const wfRes = await app!.inject({
      method: 'POST',
      url: '/v1/workflows',
      headers: { authorization: `Bearer ${apiToken}`, 'x-actor-id': 'integration-researcher' },
      payload: {
        targetRecordId,
        programSlug,
        repositoryUrl: 'https://github.com/example/runner-target',
        sourceCommit,
        chainId: 31337,
        targetAddresses: [targetAddress],
        forkBlock: 200,
        requestedMethods: ['local-test'],
        findingId: 'runner-run-test',
        title: 'Runner lease test',
      },
    });
    expect(wfRes.statusCode).toBe(201);
    const workflowId = wfRes.json<{ id: string }>().id;

    // Approve run for fixed suite 'build'
    const approveRes = await app!.inject({
      method: 'POST',
      url: `/v1/workflows/${workflowId}/approve-run`,
      headers: { 'x-approval-token': approvalToken, 'x-actor-id': 'integration-approver' },
      payload: {
        suiteId: 'build',
        rationale: 'Integration test approved build',
      },
    });
    expect(approveRes.statusCode).toBe(202);
    const runId = approveRes.json<{ runId: string }>().runId;

    // Claim run
    const claimRes = await app!.inject({
      method: 'POST',
      url: '/v1/runner/claim',
      headers: {
        'x-runner-token': issuedRunnerToken,
        'x-runner-id': runnerId,
      },
    });
    expect(claimRes.statusCode).toBe(200);
    const claimData = claimRes.json<{ run: { id: string }; leaseToken: string }>();
    expect(claimData.run.id).toBe(runId);
    expect(claimData.leaseToken).toBeDefined();

    // Negative test: posting receipt with invalid signature is rejected
    const badReceiptRes = await app!.inject({
      method: 'POST',
      url: `/v1/workflows/${workflowId}/runs/${runId}/receipt`,
      headers: {
        'x-runner-token': issuedRunnerToken,
        'x-runner-id': runnerId,
        'x-run-lease-token': claimData.leaseToken,
      },
      payload: {
        schemaVersion: 1,
        signatureAlgorithm: 'ed25519',
        runId,
        targetRecordId,
        runnerId,
        suiteId: 'build',
        repositoryUrl: 'https://github.com/example/runner-target',
        sourceCommit,
        chainId: 31337,
        forkBlock: 200,
        commandProfileId: 'foundry-build-v1',
        toolVersions: { runnerImage: 'foundry:latest' },
        exitCode: 0,
        timedOut: false,
        assertions: [{ id: 'build_completed', outcome: 'passed', detail: 'test' }],
        logArtifact: { name: 'run.log', uri: 'art-1', sha256: 'a'.repeat(64), mediaType: 'text/plain', byteLength: 10 },
        artifacts: [],
        startedAt: new Date().toISOString(),
        completedAt: new Date().toISOString(),
        signature: 'deadbeef'.repeat(16), // invalid signature
      },
    });
    expect(badReceiptRes.statusCode).toBe(400);

    // Negative test: altered artifact upload (expected sha256 mismatch)
    const content = Buffer.from('hello test bytes').toString('base64');
    const badArtifactRes = await app!.inject({
      method: 'POST',
      url: `/v1/workflows/${workflowId}/artifacts`,
      headers: {
        'x-runner-token': issuedRunnerToken,
        'x-runner-id': runnerId,
        'x-run-lease-token': claimData.leaseToken,
      },
      payload: {
        name: 'test.log',
        mediaType: 'text/plain',
        contentBase64: content,
        expectedSha256: '0'.repeat(64), // deliberately wrong sha256
        targetRecordId,
      },
    });
    expect(badArtifactRes.statusCode).toBe(400);
  });
});
