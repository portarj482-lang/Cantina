import { describe, expect, it } from 'vitest';
import { assertTransition, canTransition } from '../src/workflows/state-machine.js';

describe('workflow state machine', () => {
  it('allows the defined forward audit lifecycle', () => {
    expect(canTransition('analysis', 'approval_pending')).toBe(true);
    expect(canTransition('execution', 'evidence_review')).toBe(true);
    expect(canTransition('independent_review', 'report_draft')).toBe(true);
  });
  it('rejects skipping directly from analysis to submission', () => {
    expect(canTransition('analysis', 'submitted')).toBe(false);
    expect(() => assertTransition('analysis', 'submitted')).toThrow('Invalid workflow transition');
  });
});
