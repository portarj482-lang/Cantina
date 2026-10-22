# Per-target bounty scan rule

Apply this rule independently to every target in every bounty. A bounty-wide scope lock is necessary but not sufficient: each target scan must bind its own target identity, source/state pin, methods, layer assignments, evidence, and disposition.

## Required record

Create one `bounties/<bounty>/target-workflows/<target-id>.md` from `global/templates/target-scan-plan.md`. Never merge two targets into one record or copy a prior target's authorization, assumptions, source pin, or PoC result. The record must identify the program and scope snapshot; target name/type; exact repository and commit or hostname/domain/address and environment; permitted methods and restrictions; expiration; assigned parent Oracle and task agents; and artifact references.

If any required scope, target identity, permission, pin, or tool status is absent, stale, conflicting, or outside scope, stop that target at the affected step. Record `BLOCKED` with the missing evidence and remediation. Do not infer permission from a bounty listing, repository presence, prior work, or a successful build.

## Five mandatory target steps

1. **Bind target and authorization.** Re-read active `state.md`, `scope.md`, and `facts.md`; verify the scope snapshot; check this exact target, environment, allowed methods, restrictions, and expiry. Record the target-specific authorization result and source. A bounty-level scope match does not prove every target or method is allowed.
2. **Pin inputs and assign the workflow.** Pin the exact source commit/tree or approved web/email target and environment. Select the applicable layers and named agents from the current registry; record parent Oracle, agent contracts, inputs/outputs, dependencies, and human gates. Do not assign tools or capabilities absent from the target's allowed methods.
3. **Analyze and falsify.** Map the target's attack surface using only approved inputs/tools. Keep observations separate from assumptions. For each candidate, record actor, preconditions, call/request sequence, expected impact, concrete falsifier, and out-of-scope/known-issue checks. Kill or narrow unsupported hypotheses promptly.
4. **Verify safely.** Run only the smallest relevant test when the user requested execution, target authorization and pins are verified, tools are approved, and the isolated environment is ready. Use a target-specific harness and controls. Otherwise leave execution `NOT_RUN` or `BLOCKED`; never substitute a generic suite or another target's PoC. Do not mutate live state, contact users, or submit findings.
5. **Seal evidence and obtain human disposition.** Record commands/tool versions, exact inputs, raw outputs, artifact hashes, limitations, and whether a result is observation, inference, or proposal. Evaluate the target's quality/readiness checks; preserve negative and inconclusive results. Require independent human review for finding/report decisions; submission remains a separate explicit human action.

## State and stop semantics

Each step records `status`, `input_pin`, `evidence`, `exceptions`, `owner`, and `next_action`. Use only `PENDING`, `PASS`, `BLOCKED`, `FAILED`, `NOT_APPLICABLE`, or `NOT_RUN`. `PASS` means the step's stated process check passed; it is not a vulnerability verdict, readiness approval, or authorization to continue past a later gate. Mark `NOT_APPLICABLE` with rationale. Do not mark a later step complete while a required earlier step is blocked.

The target record is append-only in operation: preserve prior observations and dispositions; add a dated correction or superseding run instead of silently rewriting a result. Do not put secrets or personal data in it.
