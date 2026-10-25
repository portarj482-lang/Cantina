# Round 8 readiness — Governed AI Operations & Rights Governance

## Added
- `src/operations`: transparent starter task classifier, fail-closed routing policy, tenant-filtered in-process audit log.
- `src/rights`: asset provenance/rights registry, explicit permitted/excluded use scopes, license grant checks, contract-grounded revenue allocation records.
- Regression tests for unknown classifications, denied tools, write-tool gating, tenant audit filtering, rights scope enforcement, and unassigned revenue.
- Demo for a read-only research route.

## Security and correctness limits
- The classifier is a keyword-based baseline, not an evaluated production classifier. Low-confidence and ambiguous requests must be reviewed.
- The router returns a decision only; it does not execute tools. A real deployment must enforce the decision again at the tool gateway.
- Tenant filtering in this in-memory example is not a substitute for database row-level security, authenticated identity, and authorization checks on every query.
- Audit logs are process-local and not durable/tamper-proof. Production needs a transactional database, restricted append-only writer, external checkpoints/signatures, retention controls, and tested restore procedures.
- Rights metadata is an evidence ledger, not proof of legal ownership or a legal opinion.
- Revenue calculations are only implemented for a simple royalty rate with a contract reference. Fixed/equity arrangements require contract-specific logic and review.
- No OpenAI user data is imported or analyzed. This project cannot determine whether OpenAI owes a user compensation; that depends on applicable agreements and law.

## Verification commands
- `npm install`
- `npm run typecheck`
- `npm test`
- `npm run demo:all`

## Promotion gates
- [ ] Dependency install and lockfile review pass.
- [ ] Strict typecheck passes in CI.
- [ ] Test suite passes on supported Node version.
- [ ] Database-backed tenant isolation and authorization tests pass.
- [ ] Independent security review of policy bypass paths.
- [ ] Legal review of rights model and all commercial agreements.
- [ ] Human approval required for writes, high-risk actions, and any monetization claims.
