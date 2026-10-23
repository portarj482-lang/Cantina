export const ORACLE_REGISTRY = Object.freeze([
  { id: 'target-record-oracle', duties: ['validate-current-scope-binding', 'exact-target-and-method', 'source-environment-pin', 'expiry'] },
  { id: 'target-dispatch-oracle', duties: ['require-target-record', 'bind-workflow-agent-and-run', 'recheck-expiry-and-scope'] },
  { id: 'verification-profile-oracle', duties: ['allowlisted-suite-selection', 'fixed-command-profile', 'deny-disabled-poc-profiles'] },
  { id: 'evidence-review-oracle', duties: ['target-bound-artifacts-and-receipts', 'preserve-negative-and-inconclusive', 'independent-human-review'] },
  { id: 'workflow-test-oracle', duties: ['valid-and-blocked-target-record-tests', 'database-and-runner-integration-readiness'] },
]);
