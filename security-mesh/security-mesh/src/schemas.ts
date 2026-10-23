import { z } from 'zod';

const shaCommit = z.string().regex(/^(?:[a-fA-F0-9]{40}|[a-fA-F0-9]{64})$/, 'must be a full 40- or 64-character commit SHA');
const sha256 = z.string().regex(/^[a-fA-F0-9]{64}$/, 'must be a SHA-256 hex digest');
const evmAddress = z.string().regex(/^0x[a-fA-F0-9]{40}$/, 'must be a 20-byte EVM address');
const safeUrl = z.string().url().refine((value: string) => value.startsWith('https://'), 'must use HTTPS');

export const methodSchema = z.enum(['static-analysis', 'local-test', 'fork-test', 'fuzz-test', 'symbolic-analysis']);
export type Method = z.infer<typeof methodSchema>;
export const scopeCreateSchema = z.object({
  programSlug: z.string().min(3).max(100).regex(/^[a-z0-9][a-z0-9-]*$/),
  repositoryUrl: safeUrl,
  sourceCommit: shaCommit,
  chainId: z.number().int().positive(),
  targetAddresses: z.array(evmAddress).min(1).max(100),
  requiredForkBlock: z.number().int().positive(),
  allowedMethods: z.array(methodSchema).min(1).max(5),
  programAuthorizationRef: z.string().min(5).max(1000),
  expiresAt: z.string().datetime({ offset: true }),
  restrictions: z.record(z.string(), z.unknown()).default({}),
}).strict();

export const workflowCreateSchema = z.object({
  targetRecordId: z.string().uuid(),
  programSlug: z.string().min(3).max(100),
  repositoryUrl: safeUrl,
  sourceCommit: shaCommit,
  chainId: z.number().int().positive(),
  targetAddresses: z.array(evmAddress).min(1).max(100),
  forkBlock: z.number().int().positive(),
  requestedMethods: z.array(methodSchema).min(1).max(5),
  findingId: z.string().max(100).optional(),
  title: z.string().min(3).max(250).default('Authorized smart-contract security workflow'),
}).strict();

export const targetRecordCreateSchema = z.object({
  scopeId: z.string().uuid(),
  targetId: z.string().min(3).max(100).regex(/^[a-z0-9][a-z0-9-]*$/),
  targetAddress: evmAddress,
  repositoryUrl: safeUrl,
  sourceCommit: shaCommit,
  chainId: z.number().int().positive(),
  forkBlock: z.number().int().positive(),
  environment: z.string().min(2).max(100),
  allowedMethods: z.array(methodSchema).min(1).max(5),
  suiteIds: z.array(z.string().min(1).max(100)).max(20).default([]),
  expiresAt: z.string().datetime({ offset: true }),
  harnessSha256: sha256.optional(),
}).strict();

export type TargetRecordCreateInput = z.infer<typeof targetRecordCreateSchema>;

export const approveRunSchema = z.object({
  suiteId: z.string().min(1).max(100),
  targetRecordId: z.string().uuid().optional(),
  rationale: z.string().min(10).max(2000),
}).strict();

export const reviewSchema = z.object({
  decision: z.enum(['accepted', 'challenged', 'rejected']),
  targetRecordId: z.string().uuid().optional(),
  summary: z.string().min(10).max(5000),
  evidenceIds: z.array(z.string().uuid()).max(100),
}).strict();

export const approvalSubmissionSchema = z.object({
  rationale: z.string().min(20).max(5000),
  reportArtifactId: z.string().uuid(),
  findingId: z.string().min(1).max(100),
  targetRecordId: z.string().uuid().optional(),
}).strict();

export const sourceManifestSchema = z.object({
  schemaVersion: z.literal(1),
  repositoryUrl: safeUrl,
  commitSha: shaCommit,
  cleanCheckout: z.literal(true),
  treeSha256: sha256,
  trackedFiles: z.array(z.object({
    path: z.string().min(1).max(1000),
    sha256,
  }).strict()).min(1).max(100_000),
}).strict();

export const artifactUploadSchema = z.object({
  name: z.string().min(1).max(255).regex(/^[a-zA-Z0-9._-]+$/),
  targetRecordId: z.string().uuid().optional(),
  mediaType: z.string().min(1).max(150),
  contentBase64: z.string().min(4).max(30_000_000),
  expectedSha256: sha256,
}).strict();

export type ScopeCreateInput = z.infer<typeof scopeCreateSchema>;
export type WorkflowCreateInput = z.infer<typeof workflowCreateSchema>;

export const executionReceiptSchema = z.object({
  schemaVersion: z.literal(1),
  signatureAlgorithm: z.enum(['hmac-sha256', 'ed25519']).optional(),
  runId: z.string().uuid(),
  targetRecordId: z.string().uuid(),
  runnerId: z.string().min(3).max(200),
  suiteId: z.string().min(1).max(100),
  repositoryUrl: safeUrl,
  sourceCommit: shaCommit,
  chainId: z.number().int().positive(),
  forkBlock: z.number().int().positive(),
  commandProfileId: z.string().min(1).max(100),
  toolVersions: z.record(z.string(), z.string()),
  exitCode: z.number().int(),
  timedOut: z.boolean(),
  assertions: z.array(z.object({
    id: z.string().min(1).max(200),
    outcome: z.enum(['passed', 'failed', 'skipped']),
    detail: z.string().max(2000).optional(),
  }).strict()).max(1000),
  logArtifact: z.object({
    name: z.string().min(1).max(255), uri: z.string().min(1).max(1000), sha256,
    mediaType: z.string().min(1).max(150), byteLength: z.number().int().nonnegative(),
  }).strict(),
  artifacts: z.array(z.object({
    name: z.string().min(1).max(255), uri: z.string().min(1).max(1000), sha256,
    mediaType: z.string().min(1).max(150), byteLength: z.number().int().nonnegative(),
  }).strict()).max(500),
  startedAt: z.string().datetime({ offset: true }),
  completedAt: z.string().datetime({ offset: true }),
  signature: z.string().regex(/^(?:[a-fA-F0-9]{64}|[a-fA-F0-9]{128})$/),
}).strict();

export const evidenceCreateSchema = z.object({
  artifactId: z.string().uuid(),
  targetRecordId: z.string().uuid().optional(),
  evidenceKind: z.enum(['rpc-observation','overlap-review','severity-review','symbolic-analysis','counterexample','impact-measurement','analysis-methodology','analysis-result','execution-output','trace','source-excerpt','source-attestation','other']),
  claim: z.string().min(10).max(5000),
  sourceRef: z.record(z.string(), z.unknown()).default({}),
  metadata: z.record(z.string(), z.unknown()).default({}),
}).strict();

export const evidenceVerifySchema = z.object({
  rationale: z.string().min(20).max(5000),
}).strict();

export const gateEvaluationSchema = z.object({
  outcome: z.enum(['passed','failed','inconclusive','not_applicable']),
  rationale: z.string().min(20).max(5000),
  evidenceIds: z.array(z.string().uuid()).max(100),
}).strict();

export const transitionSchema = z.object({
  to: z.enum(['analysis','approval_pending','impact_review','independent_review']),
  reason: z.string().min(20).max(2000),
}).strict();

export const webScopeCreateSchema = z.object({
  programSlug: z.string().min(3).max(100).regex(/^[a-z0-9][a-z0-9-]*$/),
  approvedHosts: z.array(z.string().min(1).max(253)).min(1).max(100),
  allowedMethods: z.array(z.enum(['passive','authenticated-test','rate-limited-active'])).min(1).max(3),
  testAccountRequired: z.boolean().default(true),
  maxRequestsPerMinute: z.number().int().min(1).max(60).default(10),
  expiresAt: z.string().datetime({ offset: true }),
  authorizationRef: z.string().min(5).max(1000),
}).strict();

export const webTargetCheckSchema = z.object({
  target: z.string().url().max(2048),
  method: z.enum(['passive','authenticated-test','rate-limited-active']),
}).strict();

export const agentTaskCreateSchema = z.object({
  agentId: z.string().min(1).max(100),
  targetRecordId: z.string().uuid().optional(),
  idempotencyKey: z.string().min(8).max(200),
  contractVersion: z.string().min(1).max(40),
  input: z.record(z.string(), z.unknown()).default({}),
  dependencyTaskIds: z.array(z.string().uuid()).max(100).default([]),
  maxAttempts: z.number().int().min(1).max(20).default(2),
}).strict();

export type WebScopeCreateInput = z.infer<typeof webScopeCreateSchema>;
