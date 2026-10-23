import { createHmac, timingSafeEqual, createHash, createPrivateKey, createPublicKey, sign as cryptoSign, verify } from 'node:crypto';
import type { ArtifactReceipt, ExecutionReceipt, GateOutcome } from '../types.js';
import type { SuiteDefinition } from '../tools/registry.js';

export interface ExpectedRun {
  runId: string;
  targetRecordId: string;
  suiteId: string;
  repositoryUrl: string;
  sourceCommit: string;
  chainId: number;
  forkBlock: number;
  commandProfileId: string;
  requiredAssertions: string[];
}

export interface ArtifactLoader {
  load(uri: string): Promise<Buffer>;
}

export interface GateCheck {
  id: string;
  outcome: GateOutcome;
  reasons: string[];
}

export type RunnerSignatureTrust = string | { ed25519PublicKeyPem: string };

function stableStringify(value: unknown): string {
  if (value === undefined) return 'null';
  if (value === null || typeof value !== 'object') return JSON.stringify(value) ?? 'null';
  if (Array.isArray(value)) return `[${value.map((item) => stableStringify(item)).join(',')}]`;
  const record = value as Record<string, unknown>;
  const keys = Object.keys(record).filter((key) => record[key] !== undefined).sort();
  return `{${keys.map((key) => `${JSON.stringify(key)}:${stableStringify(record[key])}`).join(',')}}`;
}

export function canonicalReceipt(receipt: ExecutionReceipt): string {
  const { signature: _signature, ...unsigned } = receipt;
  return stableStringify(unsigned);
}

export function signReceipt(receipt: Omit<ExecutionReceipt, 'signature'>, secret: string): string {
  return createHmac('sha256', secret).update(stableStringify(receipt)).digest('hex');
}

export function signReceiptEd25519(receipt: Omit<ExecutionReceipt, 'signature'>, privateKeyPem: string): string {
  return cryptoSign(null, Buffer.from(stableStringify(receipt)), createPrivateKey(privateKeyPem)).toString('hex');
}

export function verifyReceiptSignature(receipt: ExecutionReceipt, trust: RunnerSignatureTrust): boolean {
  const payload = Buffer.from(canonicalReceipt(receipt));
  if (receipt.signatureAlgorithm === 'ed25519') {
    if (typeof trust === 'string' || !/^[a-fA-F0-9]{128}$/.test(receipt.signature)) return false;
    try {
      return verify(null, payload, createPublicKey(trust.ed25519PublicKeyPem), Buffer.from(receipt.signature, 'hex'));
    } catch { return false; }
  }
  if (receipt.signatureAlgorithm && receipt.signatureAlgorithm !== 'hmac-sha256') return false;
  if (typeof trust !== 'string' || !/^[a-fA-F0-9]{64}$/.test(receipt.signature)) return false;
  const expected = createHmac('sha256', trust).update(payload).digest();
  const provided = Buffer.from(receipt.signature, 'hex');
  return provided.length === expected.length && timingSafeEqual(provided, expected);
}

function digestHex(bytes: Buffer): string {
  return createHash('sha256').update(bytes).digest('hex');
}

function validArtifactShape(artifact: ArtifactReceipt): boolean {
  return artifact.name.length > 0 && artifact.uri.length > 0 && /^[a-fA-F0-9]{64}$/.test(artifact.sha256)
    && Number.isSafeInteger(artifact.byteLength) && artifact.byteLength >= 0 && artifact.mediaType.length > 0;
}

export async function verifyExecutionReceipt(
  receipt: ExecutionReceipt,
  expected: ExpectedRun,
  suite: SuiteDefinition,
  trustedRunnerId: string,
  runnerTrust: RunnerSignatureTrust,
  loader: ArtifactLoader,
): Promise<GateCheck[]> {
  const checks: GateCheck[] = [];
  const add = (id: string, reasons: string[]) => checks.push({ id, outcome: reasons.length ? 'failed' : 'passed', reasons });

  const identityErrors: string[] = [];
  if (receipt.schemaVersion !== 1) identityErrors.push('Unsupported receipt schema version.');
  if (receipt.runId !== expected.runId) identityErrors.push('Run ID mismatch.');
  if (receipt.targetRecordId !== expected.targetRecordId) identityErrors.push('Target record ID mismatch.');
  if (receipt.runnerId !== trustedRunnerId) identityErrors.push('Runner identity is not trusted.');
  if (receipt.suiteId !== expected.suiteId || receipt.suiteId !== suite.id) identityErrors.push('Suite ID mismatch.');
  if (receipt.repositoryUrl.replace(/\/+$/, '').toLowerCase() !== expected.repositoryUrl.replace(/\/+$/, '').toLowerCase()) identityErrors.push('Repository identity mismatch.');
  if (receipt.sourceCommit.toLowerCase() !== expected.sourceCommit.toLowerCase()) identityErrors.push('Source commit mismatch.');
  if (receipt.chainId !== expected.chainId) identityErrors.push('Chain ID mismatch.');
  if (receipt.forkBlock !== expected.forkBlock || receipt.forkBlock <= 0) identityErrors.push('Fork block mismatch or invalid nonzero block.');
  if (receipt.commandProfileId !== expected.commandProfileId || receipt.commandProfileId !== suite.commandProfileId) identityErrors.push('Command profile mismatch.');
  if (!Number.isInteger(receipt.exitCode)) identityErrors.push('Missing or invalid process exit code.');
  if (!Number.isFinite(Date.parse(receipt.startedAt)) || !Number.isFinite(Date.parse(receipt.completedAt)) || Date.parse(receipt.completedAt) < Date.parse(receipt.startedAt)) identityErrors.push('Invalid execution timestamps.');
  add('receipt_identity', identityErrors);

  add('receipt_signature', verifyReceiptSignature(receipt, runnerTrust) ? [] : ['Runner receipt signature verification failed.']);

  const assertionErrors: string[] = [];
  const observed = new Map(receipt.assertions.map((assertion) => [assertion.id, assertion.outcome]));
  for (const required of expected.requiredAssertions) {
    if (observed.get(required) !== 'passed') assertionErrors.push(`Required assertion '${required}' was absent or not passed.`);
  }
  if (receipt.exitCode !== 0) assertionErrors.push(`Runner process exited with ${receipt.exitCode}.`);
  if (receipt.timedOut) assertionErrors.push('Runner marked the execution timed out.');
  add('required_assertions', assertionErrors);

  const artifacts = [receipt.logArtifact, ...receipt.artifacts];
  const artifactErrors: string[] = [];
  if (!artifacts.every(validArtifactShape)) artifactErrors.push('One or more artifact descriptors are malformed.');
  if (artifacts.some((artifact) => artifact.uri.startsWith('file:') || artifact.uri.includes('..'))) artifactErrors.push('Artifact URI is not permitted.');
  if (!artifactErrors.length) {
    for (const artifact of artifacts) {
      try {
        const bytes = await loader.load(artifact.uri);
        if (bytes.byteLength !== artifact.byteLength) artifactErrors.push(`Artifact byte length mismatch: ${artifact.name}.`);
        if (digestHex(bytes).toLowerCase() !== artifact.sha256.toLowerCase()) artifactErrors.push(`Artifact SHA-256 mismatch: ${artifact.name}.`);
      } catch {
        artifactErrors.push(`Artifact bytes could not be retrieved: ${artifact.name}.`);
      }
    }
  }
  add('artifact_integrity', artifactErrors);

  return checks;
}
