#!/usr/bin/env node
import { spawn } from 'node:child_process';
import { setTimeout as delay } from 'node:timers/promises';
import { fileURLToPath } from 'node:url';

const base = process.env.SECURITY_MESH_API_URL?.replace(/\/$/, '');
const runnerId = process.env.RUNNER_ID;
const runnerToken = process.env.RUNNER_TOKEN;
const pollMs = Math.max(1000, Math.min(30000, Number(process.env.RUNNER_POLL_MS) || 3000));
if (!base || !runnerId || !runnerToken) throw new Error('Set SECURITY_MESH_API_URL, RUNNER_ID, and registered RUNNER_TOKEN.');
const baseUrl = new URL(base);
if (baseUrl.protocol !== 'https:' && !['localhost', '127.0.0.1', '::1'].includes(baseUrl.hostname)) throw new Error('Runner API must use HTTPS except for loopback development.');
let stopping = false;
process.once('SIGINT', () => { stopping = true; });
process.once('SIGTERM', () => { stopping = true; });

async function claim() {
  const response = await fetch(`${base}/v1/runner/claim`, { method: 'POST', headers: { 'x-runner-id': runnerId, 'x-runner-token': runnerToken } });
  if (!response.ok) throw new Error(`Runner claim failed (${response.status}): ${(await response.text()).slice(0, 500)}`);
  return response.json();
}
while (!stopping) {
  try {
    const claimData = await claim();
    const { run } = claimData;
    if (!run) { await delay(pollMs); continue; }
    const childEnv = { ...process.env, RUN_LEASE_TOKEN: run.lease_token, RUNNER_CLAIM_JSON: JSON.stringify({ run, workflow: claimData.workflow, scope: claimData.scope, targetRecord: claimData.targetRecord ?? claimData.target }) };
    const child = spawn(process.execPath, [fileURLToPath(new URL('./run.mjs', import.meta.url)), run.workflowId, run.id], { stdio: 'inherit', windowsHide: true, env: childEnv });
    const heartbeat = setInterval(async () => {
      try {
        const response = await fetch(`${base}/v1/runner/renew`, { method: 'POST', headers: { 'content-type': 'application/json', 'x-runner-id': runnerId, 'x-runner-token': runnerToken }, body: JSON.stringify({ runId: run.id, leaseToken: run.lease_token }) });
        if (!response.ok) child.kill();
      } catch { child.kill(); }
    }, 60_000);
    try { await new Promise((resolve, reject) => { child.once('error', reject); child.once('close', (code) => code === 0 ? resolve() : reject(new Error(`Run process exited ${code}`))); }); }
    finally { clearInterval(heartbeat); }
  } catch (error) {
    console.error(error instanceof Error ? error.message : 'Runner worker error');
    await delay(pollMs);
  }
}
