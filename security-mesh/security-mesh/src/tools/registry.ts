import type { Method } from '../schemas.js';

export interface SuiteDefinition {
  id: string;
  description: string;
  requiredMethod: Method;
  requiredAssertions: string[];
  dispatchEnabled: boolean;
  commandProfileId: string;
}

/** Immutable allowlist only. There is intentionally no command string in an API request. */
export const SUITES: Readonly<Record<string, SuiteDefinition>> = Object.freeze({
  build: {
    id: 'build', description: 'Compile the pinned target in an isolated worker.', requiredMethod: 'local-test',
    requiredAssertions: ['build_completed'], dispatchEnabled: true, commandProfileId: 'foundry-build-v1',
  },
  'baseline-tests': {
    id: 'baseline-tests', description: 'Run the approved baseline test profile.', requiredMethod: 'local-test',
    requiredAssertions: ['baseline_passed'], dispatchEnabled: true, commandProfileId: 'foundry-baseline-v1',
  },
  slither: {
    id: 'slither', description: 'Run fixed-profile Slither static analysis in the isolated offline runner.', requiredMethod: 'static-analysis',
    requiredAssertions: ['slither_analysis_completed'], dispatchEnabled: true, commandProfileId: 'slither-static-v1',
  },
  revocation: {
    id: 'revocation', description: 'Evaluate the approved owner-revocation hypothesis harness.', requiredMethod: 'fork-test',
    requiredAssertions: ['valid_pre_revocation_signature', 'same_digest_and_signature', 'post_revocation_erc1271_accepts_same_signature'], dispatchEnabled: false, commandProfileId: 'f001-revocation-v1',
  },
  'permit2-fork': {
    id: 'permit2-fork', description: 'Evaluate the approved downstream Permit2 impact harness.', requiredMethod: 'fork-test',
    requiredAssertions: ['permit2_prerequisites_verified', 'balance_delta_measured'], dispatchEnabled: false, commandProfileId: 'f001-permit2-v1',
  },
  'patched-negative-control': {
    id: 'patched-negative-control', description: 'Run the same assertions against an independently verified patched control.', requiredMethod: 'local-test',
    requiredAssertions: ['post_revocation_signature_rejected_by_patch'], dispatchEnabled: false, commandProfileId: 'negative-control-v1',
  },
});

export function getSuite(id: string): SuiteDefinition | undefined {
  return SUITES[id];
}
