import { z } from 'zod';

export const triageInputSchema = z.object({
  findingTitle: z.string().trim().min(1).max(250),
  hypothesis: z.string().trim().min(1).max(3_000),
  sourceExcerpt: z.string().trim().min(1).max(6_000),
  observedEvidence: z.array(z.object({
    kind: z.string().trim().min(1).max(64),
    summary: z.string().trim().min(1).max(800),
    verified: z.boolean(),
  }).strict()).max(10),
}).strict();

export const geminiTriageRequestSchema = triageInputSchema.extend({
  externalProcessingApproved: z.literal(true),
}).strict().superRefine((value, context) => {
  if (Buffer.byteLength(JSON.stringify(value), 'utf8') > 24_000) {
    context.addIssue({ code: 'custom', message: 'Gemini triage payload exceeds 24 KB.' });
  }
});

export const triageSuggestionSchema = z.object({
  summary: z.string().trim().min(1).max(3_000),
  confirmationConditions: z.array(z.string().trim().min(1).max(500)).max(20),
  falsificationConditions: z.array(z.string().trim().min(1).max(500)).max(20),
  uncertainties: z.array(z.string().trim().min(1).max(500)).max(20),
}).strict();

export type TriageInput = z.infer<typeof triageInputSchema>;
export type TriageSuggestion = z.infer<typeof triageSuggestionSchema>;
