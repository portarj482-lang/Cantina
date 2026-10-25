# Round 7 Readiness — GUMC CPI Extended Expansion

## Round 7 objective

Treat this round as a hardening and verification gate, not a claim of production readiness. Preserve fail-closed behavior, explicitly test known failure modes, and make the checks repeatable on a clean Node.js environment.

## Fixes included in v0.4.1

- Added explicit Node.js/npm engine requirements and named unit/full-check/demo scripts.
- Added CI that installs from the lockfile, runs TypeScript typechecking, runs all unit tests, and executes the demos.
- CCI rejects invalid assessment-specific time and memory budgets.
- CCI no longer labels a supplied candidate as an `exact` plan; it defers to an independent verifier because the planner itself does not verify candidate correctness.
- Audit canonicalization explicitly handles `undefined` and rejects unsupported/non-finite values instead of silently hashing ambiguous JSON-like input.
- Added regression tests for invalid budgets, candidate verification boundaries, and malformed temporal mapping output.

## Round 7 acceptance gates

1. Dependency installation completes in a clean CI environment. Commit a generated `package-lock.json` before treating dependency resolution as fully reproducible.
2. `npm run typecheck` passes with strict TypeScript settings.
3. `npm run test:unit` passes on the pinned Node version.
4. `npm run demo:all` completes without errors.
5. CI runs on pushes and pull requests.
6. Unknown temporal mappings defer; invalid mapping outputs reject/isolate and preserve trusted state.
7. CCI never claims to prove P vs NP membership or verify a candidate itself.
8. Production integration remains disabled until authenticated governance, durable persistence, cryptographic approval verification, and an independent evidence gate exist.

## Known remaining gaps

- No PostgreSQL persistence or authenticated identity/governance service.
- Audit chain is in-memory; a privileged attacker can rewrite the full chain. A production audit requires durable storage and externally anchored checkpoints or equivalent controls.
- No deployed sandbox, unrestricted runner, or live smart-contract execution integration.
- No formal proof of conversion reversibility or complexity classification.
- This scaffold does not confirm the Coinbase/Base F-001 vulnerability; any such finding needs independently reproducible evidence and human approval.

## Run locally

Use Node.js 22.16.0 or newer and npm 10 or newer:

```bash
npm install
npm run typecheck
npm run test:unit
npm run demo:all
```

The release is Round 7-ready for a **verification pass** only after all four commands pass in a clean environment. Do not mark the release production-ready based solely on this document.

## Verification status in this build environment

- Unit tests: **30 passed, 0 failed** on Node.js 22.16.0 using Node's experimental TypeScript stripping.
- Demo commands: run separately during packaging; results are recorded in the release notes.
- TypeScript typecheck: **not verified locally** because dependencies could not be installed in this environment and `@types/node` is absent. CI is configured to install dependencies and run the strict typecheck, but the release must not be called fully verified until CI passes.
- Lockfile: not generated because the package registry was unreachable from this build environment. A committed lockfile remains a Round 7 gate for deterministic dependency resolution.
