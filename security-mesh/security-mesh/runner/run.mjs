#!/usr/bin/env node
import { spawn } from 'node:child_process';
import { createHash, sign } from 'node:crypto';
import { access, mkdtemp, readFile, rm, stat } from 'node:fs/promises';
import { resolve4 } from 'node:dns/promises';
import { isIP } from 'node:net';
import { tmpdir } from 'node:os';
import { isAbsolute, join, resolve } from 'node:path';
const profiles = Object.freeze({
  build: { commandProfileId: 'foundry-build-v1', requiredMethod: 'local-test', assertion: 'build_completed', imageEnv: 'FOUNDRY_RUNNER_IMAGE', script: 'tar -xf /input/source.tar -C /work && cd /work && forge build --offline' },
  'baseline-tests': { commandProfileId: 'foundry-baseline-v1', requiredMethod: 'local-test', assertion: 'baseline_passed', imageEnv: 'FOUNDRY_RUNNER_IMAGE', script: 'tar -xf /input/source.tar -C /work && cd /work && forge test --offline' },
  slither: { commandProfileId: 'slither-static-v1', requiredMethod: 'static-analysis', assertion: 'slither_analysis_completed', imageEnv: 'SLITHER_RUNNER_IMAGE', script: 'tar -xf /input/source.tar -C /work && cd /work && slither . --json - --fail-none' },
});
const maxLogBytes = 10 * 1024 * 1024;
const timeoutMs = 10 * 60 * 1000;
let dockerCli = process.env.DOCKER_CLI || 'docker';

async function resolveDockerCli() {
  if (process.env.DOCKER_CLI) return process.env.DOCKER_CLI;
  if (process.platform !== 'win32') return 'docker';
  const candidates = [
    join(process.env.ProgramFiles || 'C:\\Program Files', 'Docker', 'Docker', 'resources', 'bin', 'docker.exe'),
    process.env.LOCALAPPDATA ? join(process.env.LOCALAPPDATA, 'Programs', 'DockerDesktop', 'resources', 'bin', 'docker.exe') : '',
  ].filter(Boolean);
  for (const candidate of candidates) {
    try { await access(candidate); return candidate; } catch { /* try next known install location */ }
  }
  return 'docker';
}

function isPublicV4(ip) {
  const [a, b, c] = ip.split('.').map(Number);
  return Number.isInteger(a) && Number.isInteger(b) && Number.isInteger(c) && !(a === 0 || a === 10 || a === 127 || a >= 224 ||
    (a === 169 && b === 254) || (a === 172 && b >= 16 && b <= 31) || (a === 192 && [0, 2, 168].includes(b)) ||
    (a === 198 && [18, 19, 51].includes(b)) || (a === 203 && b === 0 && c === 113) || (a === 100 && b >= 64 && b <= 127));
}

function fail(message) { console.error(message); process.exitCode = 1; }
function stable(value) {
  if (value === null || typeof value !== 'object') return JSON.stringify(value);
  if (Array.isArray(value)) return `[${value.map(stable).join(',')}]`;
  return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${stable(value[key])}`).join(',')}}`;
}
function sha(bytes) { return createHash('sha256').update(bytes).digest('hex'); }
function command(bin, args, options = {}) {
  return new Promise((resolvePromise, reject) => {
    const { timeoutMs: commandTimeoutMs, ...spawnOptions } = options;
    const child = spawn(bin, args, { stdio: ['ignore', 'pipe', 'pipe'], windowsHide: true, ...spawnOptions });
    let stdout = '', stderr = '';
    const timer = commandTimeoutMs ? setTimeout(() => child.kill(), commandTimeoutMs) : undefined;
    child.stdout?.on('data', (chunk) => { stdout += chunk.toString(); });
    child.stderr?.on('data', (chunk) => { stderr += chunk.toString(); });
    child.on('error', (error) => { if (timer) clearTimeout(timer); reject(error); });
    child.on('close', (code) => { if (timer) clearTimeout(timer); code === 0 ? resolvePromise({ stdout, stderr }) : reject(new Error(`${bin} failed (${code}): ${stderr || stdout}`)); });
  });
}
async function git(source, args) {
  const result = await command('git', ['-C', source, ...args]);
  return result.stdout.trim();
}
async function api(url, { apiToken, runnerToken, runnerId, leaseToken } = {}, body) {
  const response = await fetch(url, { method: body ? 'POST' : 'GET', headers: { ...(apiToken ? { authorization: `Bearer ${apiToken}` } : {}), ...(runnerToken ? { 'x-runner-token': runnerToken, 'x-runner-id': runnerId } : {}), ...(leaseToken ? { 'x-run-lease-token': leaseToken } : {}), ...(body ? { 'content-type': 'application/json' } : {}) }, ...(body ? { body: JSON.stringify(body) } : {}) });
  const text = await response.text();
  let value;
  try { value = JSON.parse(text); } catch { value = { error: text.slice(0, 1000) }; }
  if (!response.ok) throw new Error(`Security Mesh API ${response.status}: ${JSON.stringify(value)}`);
  return value;
}

async function main() {
  const [workflowId, runId, sourceArg] = process.argv.slice(2);
  const source = sourceArg ? resolve(sourceArg) : '';
  const apiBase = process.env.SECURITY_MESH_API_URL;
  const apiToken = process.env.API_TOKEN;
  const runnerToken = process.env.RUNNER_TOKEN;
  const runnerId = process.env.RUNNER_ID;
  const privateKeyPem = process.env.RUNNER_PRIVATE_KEY_PEM?.replace(/\\n/g, '\n');
  if (!workflowId || !runId || (source && !isAbsolute(source))) throw new Error('Usage: node runner/run.mjs <workflow-id> <run-id> [absolute-clean-checkout].');
  if (!apiBase || !runnerToken || !runnerId || !privateKeyPem) throw new Error('Set SECURITY_MESH_API_URL, runner identity credentials, RUNNER_ID, and RUNNER_PRIVATE_KEY_PEM.');
  dockerCli = await resolveDockerCli();
  await command(dockerCli, ['info', '--format', '{{.ServerVersion}}'], { timeoutMs: 15_000 });
  if (source && (source.includes(',') || source.includes('\n'))) throw new Error('Checkout path cannot contain commas or newlines.');
  const baseUrl = new URL(apiBase);
  if (baseUrl.protocol !== 'https:' && !['localhost', '127.0.0.1', '::1'].includes(baseUrl.hostname)) throw new Error('Runner API must use HTTPS except for loopback development.');

  const base = apiBase.replace(/\/$/, '');
  const runnerContext = { apiToken, runnerToken, runnerId, leaseToken: process.env.RUN_LEASE_TOKEN };
  let claim;
  try { claim = process.env.RUNNER_CLAIM_JSON ? JSON.parse(process.env.RUNNER_CLAIM_JSON) : undefined; }
  catch { throw new Error('Runner claim payload is invalid.'); }
  const data = claim ?? await api(`${base}/v1/workflows/${workflowId}`, runnerContext);
  const workflow = data.workflow;
  const run = claim?.run ?? (data.runs ?? []).find((item) => item.id === runId);
  if (!workflow || !run || !['queued','running'].includes(run.status) || workflow.approval_status !== 'approved' || (run.runner_id && run.runner_id !== runnerId)) throw new Error('The workflow and a human-approved run assigned to this runner must exist.');
  if (!run.target_record_id || run.target_record_id !== workflow.target_record_id) throw new Error('The run is missing a matching target-record authorization binding.');
  if (claim?.targetRecord && claim.targetRecord.id && claim.targetRecord.id !== run.target_record_id) {
    throw new Error('Target record in runner claim does not match run target-record binding.');
  }
  const targetCheck = claim?.targetCheck ?? (claim?.targetRecord ? {
    valid: !claim.targetRecord.disabled_at && !claim.targetRecord.disabledAt && Date.parse(claim.targetRecord.expires_at || claim.targetRecord.expiresAt) > Date.now(),
    oracle: {
      outcome: (!claim.targetRecord.disabled_at && !claim.targetRecord.disabledAt && Date.parse(claim.targetRecord.expires_at || claim.targetRecord.expiresAt) > Date.now()) ? 'allow' : 'deny',
      reasons: (!claim.targetRecord.disabled_at && !claim.targetRecord.disabledAt && Date.parse(claim.targetRecord.expires_at || claim.targetRecord.expiresAt) > Date.now()) ? [] : ['Target record is disabled, expired, or invalid.'],
    },
  } : await api(`${base}/v1/target-records/${run.target_record_id}/check`, runnerContext));
  if (!targetCheck || !targetCheck.valid || targetCheck.oracle?.outcome !== 'allow') throw new Error(`Target record authorization verification failed: ${targetCheck?.oracle?.reasons?.join(' ') || 'target record invalid or expired'}`);
  const profile = profiles[run.suite_id];
  if (!profile || run.command_profile_id !== profile.commandProfileId) throw new Error(`Suite '${run.suite_id}' has no implemented safe command profile.`);
  const image = process.env[profile.imageEnv];
  if (!image || !/@sha256:[a-f0-9]{64}$/i.test(image)) throw new Error(`${profile.imageEnv} must be a locally available image pinned by sha256 digest.`);
  if (String(workflow.source_commit).toLowerCase() !== String(run.source_commit).toLowerCase()) throw new Error('Workflow and approved run source commits disagree.');
  const normalizeRepo = (value) => value.replace(/\/+$/, '').replace(/\.git$/i, '').toLowerCase();
  const scope = claim?.scope ?? ((await api(`${base}/v1/scopes`, runnerContext)).scopes ?? []).find((item) => item.id === workflow.scope_id);
  if (!scope || scope.disabled_at || Date.parse(scope.expires_at) <= Date.now()) throw new Error('The approved source scope is absent, expired, or disabled.');
  if (normalizeRepo(String(scope.repository_url)) !== normalizeRepo(String(run.repository_url)) || String(scope.source_commit).toLowerCase() !== String(run.source_commit).toLowerCase() || Number(scope.chain_id) !== Number(run.chain_id) || Number(scope.required_fork_block) !== Number(run.fork_block) || !(scope.allowed_methods ?? []).includes(profile.requiredMethod)) throw new Error('Queued run no longer matches its registered scope.');
  const approvedAddresses = new Set((scope.target_addresses ?? []).map((address) => String(address).toLowerCase()));
  if ((workflow.target_addresses ?? []).some((address) => !approvedAddresses.has(String(address).toLowerCase()))) throw new Error('Workflow targets no longer match the registered source scope.');

  const temp = await mkdtemp(resolve(tmpdir(), 'security-mesh-runner-'));
  const sourceArchive = resolve(temp, 'source.tar');
  const cidPath = resolve(temp, 'container.id');
  let log = '';
  let timedOut = false;
  let exitCode = 1;
  const startedAt = new Date().toISOString();
  try {
    const gitEnv = { ...process.env, GIT_CONFIG_NOSYSTEM: '1', GIT_CONFIG_GLOBAL: resolve(temp, 'empty.gitconfig'), GIT_TERMINAL_PROMPT: '0', GIT_ALLOW_PROTOCOL: 'https' };
    let archiveRepo = source;
    if (source) {
      if (normalizeRepo(await git(source, ['remote', 'get-url', 'origin'])) !== normalizeRepo(String(run.repository_url))) throw new Error('Checkout origin does not match the approved repository.');
      if ((await git(source, ['rev-parse', 'HEAD'])).toLowerCase() !== String(run.source_commit).toLowerCase()) throw new Error('Checkout HEAD does not match the approved run commit.');
      if (await git(source, ['status', '--porcelain'])) throw new Error('Checkout must be clean.');
      archiveRepo = source;
    } else {
      const repository = new URL(String(run.repository_url));
      if (repository.protocol !== 'https:' || repository.username || repository.password || repository.port || !['github.com','gitlab.com','bitbucket.org'].includes(repository.hostname.toLowerCase())) throw new Error('Automatic source fetch supports only public HTTPS GitHub, GitLab, and Bitbucket repositories.');
      const resolved = await resolve4(repository.hostname);
      if (!resolved.length || resolved.some((ip) => isIP(ip) !== 4 || !isPublicV4(ip))) throw new Error('Repository host did not resolve exclusively to public IPv4 addresses.');
      archiveRepo = resolve(temp, 'repo.git');
      await command('git', ['init', '--bare', archiveRepo], { env: gitEnv, timeoutMs: 120_000 });
      await command('git', ['--git-dir', archiveRepo, 'remote', 'add', 'origin', String(run.repository_url)], { env: gitEnv, timeoutMs: 120_000 });
      await command('git', ['--git-dir', archiveRepo, 'fetch', '--no-tags', 'origin', String(run.source_commit)], { env: gitEnv, timeoutMs: 120_000 });
      const treeEntries = await command('git', ['--git-dir', archiveRepo, 'ls-tree', '-r', String(run.source_commit)], { env: gitEnv, timeoutMs: 120_000 });
      if (treeEntries.stdout.split(/\r?\n/).some((line) => /^(?:120000|160000)\s/.test(line))) throw new Error('Symlinks and submodules are not supported by this runner.');
    }
    await command('git', [...(source ? ['-C', source] : ['--git-dir', archiveRepo]), 'archive', '--format=tar', '--output', sourceArchive, String(run.source_commit)], { env: gitEnv, timeoutMs: 120_000 });
    if ((await stat(sourceArchive)).size > 500 * 1024 * 1024) throw new Error('Pinned source archive exceeds the 500 MB runner limit.');
    const dockerArgs = [
      'run', '--rm', '--pull=never', '--cidfile', cidPath,
      '--network=none', '--read-only', '--cap-drop=ALL', '--security-opt=no-new-privileges:true',
      '--pids-limit=256', '--memory=4g', '--cpus=2', '--user=10001:10001',
      '--tmpfs', '/work:rw,nosuid,size=4g,uid=10001,gid=10001', '--tmpfs', '/tmp:rw,nosuid,size=1g,uid=10001,gid=10001',
      '--mount', `type=bind,source=${sourceArchive},target=/input/source.tar,readonly`,
      '--env', 'HOME=/tmp', '--env', 'FOUNDRY_OUT=/tmp/out', '--env', 'FOUNDRY_CACHE_PATH=/tmp/cache',
      '--entrypoint', '/bin/sh', image, '-c', profile.script,
    ];
    const child = spawn(dockerCli, dockerArgs, { stdio: ['ignore', 'pipe', 'pipe'], windowsHide: true });
    let logTruncated = false;
    const append = (chunk) => {
      if (Buffer.byteLength(log) >= maxLogBytes) { logTruncated = true; return; }
      const remaining = maxLogBytes - Buffer.byteLength(log);
      const value = chunk.toString();
      log += value.slice(0, remaining);
      if (Buffer.byteLength(value) > remaining) logTruncated = true;
    };
    child.stdout.on('data', append); child.stderr.on('data', append);
    const status = await new Promise((resolvePromise, reject) => {
      let done = false;
      const timer = setTimeout(async () => {
        timedOut = true;
        try { const cid = (await readFile(cidPath, 'utf8')).trim(); if (cid) await command(dockerCli, ['stop', '--time', '2', cid]); } catch { /* container may not have started */ }
        if (!done) child.kill();
      }, timeoutMs);
      child.on('error', (error) => { if (!done) { done = true; clearTimeout(timer); reject(error); } });
      child.on('close', (code) => { if (!done) { done = true; clearTimeout(timer); resolvePromise(code ?? 1); } });
    });
    exitCode = Number(status);
    if (timedOut) log += '\nRunner timeout exceeded; container was stopped.\n';
    if (logTruncated) log += '\nRunner log truncated at the configured size limit.\n';
  } catch (error) {
    log += `\nRunner error: ${error instanceof Error ? error.message : 'unknown error'}\n`;
  }
  const completedAt = new Date().toISOString();
  const bytes = Buffer.from(log || 'Runner produced no output.\n');
  if (bytes.byteLength > maxLogBytes) throw new Error('Runner output exceeded the artifact size limit.');
  try {
    const uploaded = await api(`${base}/v1/workflows/${workflowId}/artifacts`, runnerContext, {
      name: `run-${runId}.log`, mediaType: 'text/plain', contentBase64: bytes.toString('base64'), expectedSha256: sha(bytes),
    });
    const baselineSummary = log.replace(/\u001b\[[0-9;]*m/g, '').match(/Suite result:\s*ok\.\s*(\d+) passed;\s*(\d+) failed/gi) ?? [];
    const baselineCounts = baselineSummary.map((line) => line.match(/(\d+) passed;\s*(\d+) failed/i)).filter(Boolean).map((match) => ({ passed: Number(match[1]), failed: Number(match[2]) }));
    const slitherCompleted = run.suite_id !== 'slither' || (/"success"\s*:\s*true/.test(log) && /"results"\s*:/.test(log));
    const assertionPassed = exitCode === 0 && !timedOut && (run.suite_id !== 'baseline-tests' || (!logTruncated && baselineCounts.length > 0 && baselineCounts.reduce((sum, item) => sum + item.passed, 0) > 0 && baselineCounts.every((item) => item.failed === 0))) && slitherCompleted;
    const receipt = {
        schemaVersion: 1, signatureAlgorithm: 'ed25519', runId, targetRecordId: run.target_record_id, runnerId, suiteId: run.suite_id,
      repositoryUrl: run.repository_url, sourceCommit: run.source_commit, chainId: Number(run.chain_id), forkBlock: Number(run.fork_block),
      commandProfileId: run.command_profile_id, toolVersions: { runnerImage: image }, exitCode, timedOut,
      assertions: [{ id: profile.assertion, outcome: assertionPassed ? 'passed' : run.suite_id === 'baseline-tests' && exitCode === 0 ? 'skipped' : 'failed', detail: run.suite_id === 'baseline-tests' ? `Offline test summary: ${baselineCounts.reduce((sum, item) => sum + item.passed, 0)} passed, ${baselineCounts.reduce((sum, item) => sum + item.failed, 0)} failed.` : run.suite_id === 'slither' ? `Static analyzer completed: ${slitherCompleted}. Findings are heuristic leads only.` : 'Process exit status from an offline, network-isolated Foundry container.' }],
      logArtifact: { name: `run-${runId}.log`, uri: uploaded.storageKey, sha256: uploaded.sha256, mediaType: 'text/plain', byteLength: uploaded.byteLength },
      artifacts: [], startedAt, completedAt,
    };
    receipt.signature = sign(null, Buffer.from(stable(receipt)), privateKeyPem).toString('hex');
    const posted = await api(`${base}/v1/workflows/${workflowId}/runs/${runId}/receipt`, runnerContext, receipt);
    console.log(JSON.stringify({ runId, executionStatus: posted.executionStatus, exitCode, timedOut, artifactId: uploaded.artifactId }));
    if (posted.executionStatus !== 'passed') process.exitCode = 1;
  } finally {
    await rm(temp, { recursive: true, force: true });
  }
}

main().catch(fail);
