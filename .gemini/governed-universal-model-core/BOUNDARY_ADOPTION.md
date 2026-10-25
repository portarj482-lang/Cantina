# Symbol Boundary implementation slice

This slice implements the first GUMC adoption boundary as an in-memory reference service plus a PostgreSQL migration. It preserves the source's operational concepts—capture without admission, provenance, explicit unknowns, quarantine, verification, reconstruction boundary, and a final fail-closed admission gate—without treating source-specific notation as executable mathematics.

## Included
- `src/boundary/types.ts`: typed records, provenance, explicit known/unknown fields, admission checks, and audit events.
- `src/boundary/service.ts`: capture, project-scoped retrieval, quarantine, revision-bound verification, independent-review admission, and transition audit events.
- `migrations/001_boundary_records.sql`: PostgreSQL persistence schema and indexes.
- `test/boundary/boundary.test.ts`: tests for provenance, unknowns, quarantine, stale revisions, evidence, reviewer separation, required checks, and project isolation.

## Security and deployment limits
- The TypeScript service is an in-memory reference implementation; state does not survive process restart and it is not a production persistence adapter.
- Apply the SQL migration only through the project's migration mechanism. Production persistence must make record mutation and audit-event insertion one transaction and enforce project authorization in the data-access layer (and preferably PostgreSQL row-level security).
- Evidence IDs are references only; the service does not verify artifact contents, signatures, RPC agreement, or tool receipts. Connect it to the existing evidence gate before treating records as security findings.
- `admitted` means this boundary service's configured checks passed; it does not itself authorize execution, submission, or bounty reporting. Keep execution, finding, review, approval, and submission statuses independent.
- The service requires the caller to supply a reviewer identity. Production must derive identity from authenticated authorization context, not trust arbitrary caller-supplied strings.
- No provider adapter, dashboard, or automatic agent write path is enabled in this slice.

## Run
```bash
npm run typecheck
npm run test:boundary
npm run test:unit
```

The repository may have pre-existing failures; record them rather than weakening controls. Existing project source should be reconciled before this slice is copied into the active WSL working tree.
