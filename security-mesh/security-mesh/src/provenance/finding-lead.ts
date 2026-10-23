import { z } from 'zod';

export const sourceSpanSchema = z.object({
  path: z.string().min(1).max(512).refine((p) => !p.startsWith('/') && !p.includes('..') && !p.includes('\\'), {
    message: 'Normalized relative source path required.',
  }),
  startLine: z.number().int().positive(),
  endLine: z.number().int().positive(),
  excerptSha256: z.string().regex(/^[0-9a-f]{64}$/i),
  rawExcerpt: z.string().max(2000),
}).refine((span) => span.endLine >= span.startLine, {
  message: 'endLine must be greater than or equal to startLine.',
});

export type SourceSpan = z.infer<typeof sourceSpanSchema>;

export const findingLeadSchema = z.object({
  id: z.string().regex(/^[A-Z]{1,8}-[0-9]{3,6}$/, { message: 'Finding lead ID must follow format F-001 or LEAD-001.' }),
  workflowId: z.string().uuid(),
  sourceCommit: z.string().regex(/^[0-9a-f]{40}$/i),
  repositoryUrl: z.string().url(),
  detector: z.object({
    tool: z.string().min(1).max(64),
    version: z.string().min(1).max(64),
    ruleId: z.string().min(1).max(128),
  }),
  sourceSpan: sourceSpanSchema,
  hypothesis: z.string().min(10).max(4000),
  confirmationChecks: z.array(z.string().min(5)).min(1),
  falsificationChecks: z.array(z.string().min(5)).min(1),
  evidenceRefs: z.array(z.string().uuid()),
  limitations: z.array(z.string()).default([]),
  status: z.enum(['candidate_lead', 'unconfirmed', 'falsified', 'evidence_supported']),
  statusHistory: z.array(
    z.object({
      status: z.string(),
      actor: z.string(),
      timestamp: z.string().datetime(),
      rationale: z.string(),
    })
  ).min(1),
});

export type FindingLead = z.infer<typeof findingLeadSchema>;

export function validateFindingLead(data: unknown): { success: true; lead: FindingLead } | { success: false; errors: string[] } {
  const result = findingLeadSchema.safeParse(data);
  if (!result.success) {
    return {
      success: false,
      errors: result.error.issues.map((i) => `${i.path.join('.')}: ${i.message}`),
    };
  }
  return { success: true, lead: result.data };
}
