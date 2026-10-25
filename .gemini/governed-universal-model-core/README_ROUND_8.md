# GUMC v0.5.0 — Governed AI Operations and Rights Governance

This expansion adds an operational classification-and-routing layer and a provenance/licensing/revenue ledger to the existing GUMC + CPI + CCI + temporal foundation.

## Core principle
Classifying a request does not authorize it. The route policy fails closed for missing identity, blocked tenants, denied users, unknown sensitivity, low-confidence classification, critical risk, and unapproved tools. Write-capable tools require a human gate. This demo never executes tools.

## New modules
- `src/operations`: request envelope, task classifier, policy router, tenant-filtered audit log.
- `src/rights`: asset registry, provenance/evidence references, explicit permitted/excluded scopes, license grants, conservative revenue allocation records.

## Quick start
Requires Node.js >=22.16.0 and npm >=10.

```bash
npm install
npm run typecheck
npm test
npm run demo:all
npm run demo:operations
```

## Commercial-rights note
The rights module is designed for assets and contracts your application is authorized to track. It does not infer a royalty or ownership right from model-training opt-in, general product terms, or the fact that an idea resembles an implemented feature. A compensation claim requires a legal and factual basis; the module therefore keeps unassigned revenue unassigned and requires contract references for royalty calculations.

See `ROUND_8_READINESS.md` and `src/rights/README.md` before production use.
