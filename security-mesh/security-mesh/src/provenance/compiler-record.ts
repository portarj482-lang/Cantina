import { z } from 'zod';

export const compilerProvenanceRecordSchema = z.object({
  recordId: z.string().uuid(),
  workflowId: z.string().uuid(),
  sourceRecordId: z.string().uuid(),
  compilerImageDigest: z.string().regex(/@[a-z0-9]+:[a-f0-9]{64}$/i, {
    message: 'Compiler image must be pinned by sha256 digest (e.g., ghcr.io/org/solc@sha256:...).',
  }),
  solcVersion: z.string().regex(/^0\.[0-9]+\.[0-9]+(?:\+commit\.[0-9a-f]{8})?$/, {
    message: 'solcVersion must be a valid semver compiler string (e.g., 0.8.24 or 0.8.24+commit.e11b9ed9).',
  }),
  settingsSha256: z.string().regex(/^[0-9a-f]{64}$/i, {
    message: 'Settings digest must be a 64-character SHA-256 hex string.',
  }),
  generatedAstSha256: z.string().regex(/^[0-9a-f]{64}$/i, {
    message: 'AST digest must be a 64-character SHA-256 hex string.',
  }),
  sourceToAstMappingCount: z.number().int().positive(),
  compiledAt: z.string().datetime(),
  outputArtifactSha256: z.string().regex(/^[0-9a-f]{64}$/i),
});

export type CompilerProvenanceRecord = z.infer<typeof compilerProvenanceRecordSchema>;

export function validateCompilerRecord(data: unknown): { success: true; record: CompilerProvenanceRecord } | { success: false; errors: string[] } {
  const result = compilerProvenanceRecordSchema.safeParse(data);
  if (!result.success) {
    return {
      success: false,
      errors: result.error.issues.map((i) => `${i.path.join('.')}: ${i.message}`),
    };
  }
  return { success: true, record: result.data };
}
