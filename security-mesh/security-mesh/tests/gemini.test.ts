import { describe, expect, it } from 'vitest';
import { geminiTriageRequestSchema, triageSuggestionSchema } from '../src/providers/gemini-schemas.js';

const validRequest = {
  findingTitle: 'Unrestricted withdrawal',
  hypothesis: 'A caller may withdraw assets belonging to another user.',
  sourceExcerpt: 'function withdraw(uint256 amount) external { balances[msg.sender] -= amount; }',
  observedEvidence: [{ kind: 'source-review', summary: 'Caller identity is used for the balance key.', verified: true }],
  externalProcessingApproved: true,
};

describe('Gemini triage boundaries', () => {
  it('requires explicit per-request external-processing consent and rejects extra fields', () => {
    expect(geminiTriageRequestSchema.safeParse(validRequest).success).toBe(true);
    expect(geminiTriageRequestSchema.safeParse({ ...validRequest, externalProcessingApproved: false }).success).toBe(false);
    expect(geminiTriageRequestSchema.safeParse({ ...validRequest, privateMetadata: 'do not send' }).success).toBe(false);
  });

  it('bounds submitted material and model output', () => {
    expect(geminiTriageRequestSchema.safeParse({ ...validRequest, sourceExcerpt: 'x'.repeat(6_001) }).success).toBe(false);
    expect(triageSuggestionSchema.safeParse({
      summary: 'Advisory only.', confirmationConditions: [], falsificationConditions: [], uncertainties: [],
    }).success).toBe(true);
    expect(triageSuggestionSchema.safeParse({
      summary: 'x'.repeat(3_001), confirmationConditions: [], falsificationConditions: [], uncertainties: [],
    }).success).toBe(false);
  });
});
