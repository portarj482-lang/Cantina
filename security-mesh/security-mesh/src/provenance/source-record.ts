import { z } from 'zod';

export const SUPPORTED_SOURCE_HOSTS = ['github.com', 'gitlab.com', 'bitbucket.org'] as const;

export const controlledSourceRecordSchema = z.object({
  recordId: z.string().uuid(),
  workflowId: z.string().uuid(),
  repositoryUrl: z.string().url().refine((url) => {
    try {
      const parsed = new URL(url);
      return parsed.protocol === 'https:' && SUPPORTED_SOURCE_HOSTS.includes(parsed.hostname.toLowerCase() as typeof SUPPORTED_SOURCE_HOSTS[number]);
    } catch {
      return false;
    }
  }, { message: 'Repository URL must use HTTPS and belong to an approved public Git host (github.com, gitlab.com, bitbucket.org).' }),
  sourceCommit: z.string().regex(/^[0-9a-f]{40}$/i, { message: 'Source commit must be a 40-character hex Git SHA.' }),
  archiveSha256: z.string().regex(/^[0-9a-f]{64}$/i, { message: 'Archive digest must be a 64-character SHA-256 hex string.' }),
  treeSha256: z.string().regex(/^[0-9a-f]{64}$/i, { message: 'Tree digest must be a 64-character SHA-256 hex string.' }),
  trackedFileCount: z.number().int().positive(),
  verifiedGitIdentity: z.boolean(),
  fetchedAt: z.string().datetime(),
  runnerId: z.string().min(3).max(128),
  provenanceStatus: z.enum(['verified', 'provisional', 'rejected']),
});

export type ControlledSourceRecord = z.infer<typeof controlledSourceRecordSchema>;

export function validateSourceRecord(data: unknown): { success: true; record: ControlledSourceRecord } | { success: false; errors: string[] } {
  const result = controlledSourceRecordSchema.safeParse(data);
  if (!result.success) {
    return {
      success: false,
      errors: result.error.issues.map((i) => `${i.path.join('.')}: ${i.message}`),
    };
  }
  return { success: true, record: result.data };
}
