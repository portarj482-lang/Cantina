# F-001 / Cantina Finding #1736 — Verification Plan

**Status:** Hypothesis only; no vulnerability verdict is encoded here.\
**Target:** Coinbase Onchain Bug Bounty on Cantina, subject to current program scope approval.\
**Primary claim to test:** The reported EIP-7702 proxy / ERC-1271 validation behavior may fail to preserve an expected owner/revocation authorization invariant.\
**Execution status:** Not run. No target repository, commit, address, fork block, RPC endpoint, or isolated runner is preconfigured by this case file.

## Safety and entry criteria

Before any test suite is enabled or dispatched, the operator must independently verify and register the live Cantina scope. Record the program rules/version or URL, repository URL, exact full commit SHA, target address(es), chain ID, nonzero pinned fork block, permitted methods, restrictions, and expiry. The API's scope record is an authorization assertion supplied by an operator; it does not itself prove Cantina authorization.

G1 cannot be satisfied by a manifest digest alone: a human reviewer must inspect a separate source-attestation artifact that binds repository identity, exact commit object, and source-line references/excerpt hashes to the scoped workflow. Until that attestation is independently reviewed and G1 is explicitly evaluated, the workflow must remain blocked before downstream analysis.

The execution profile for this case must remain local/fork read-only. It must not broadcast transactions, use production signing keys, send arbitrary RPC writes, or attempt to affect third-party state. The initial API implementation is queue-only and has no actual Foundry worker. A queued suite is not an executed test.

## Root hypothesis and falsification criteria

Treat the finding as a falsifiable hypothesis, not a fact:

> For the exact scoped implementation and pinned state, a signature accepted under a previously valid owner configuration may continue to validate after the relevant owner authorization has been revoked, because one validation path reaches a fallback that does not enforce the intended account-ownership/revocation invariant.

This statement is a test hypothesis, not a verified source description. Revise it if the pinned code or real call semantics differ.

**Evidence that would support the hypothesis:**

1. A valid baseline signature is accepted for the intended wallet/account and exact digest.
2. The test performs the in-sandbox state transition that removes/revokes the relevant owner (or faithfully models the protocol's authorized revocation state transition).
3. With the same digest, signature bytes, account identity, code/implementation context, and other relevant inputs, the post-revocation ERC-1271 validation still returns the success magic value / expected success outcome.
4. The observed call path and resulting behavior are consistent with the claimed fallback and cannot be explained by a test harness mismatch, alternate owner, stale state, digest change, or incorrect EIP-7702 delegation setup.
5. The exact assertions, logs, trace, source manifest, chain ID, fork block, tool versions, and runner-signed receipt pass deterministic verification.

**Evidence that would falsify or materially narrow it:**

- The valid baseline fails; the test is invalid until corrected.
- The post-revocation validation rejects the identical signature as expected.
- The signature/digest/account/implementation differs between pre- and post-revocation checks.
- The purported fallback does not exist in the exact pinned revision or is not reached in the deployed call path.
- The behavior requires an out-of-scope configuration, unavailable state, or assumption inconsistent with the target's documented intended behavior.
- A valid negative control does not distinguish the alleged vulnerable behavior from normal behavior.

## Required test matrix

| Case | Suite ID | Preconditions | Expected assertion contract | Purpose |
|---|---|---|---|---|
| Baseline build | `build` | Exact clean source commit and compiler config | `build_completed` | Establish the harness and source can build. |
| Baseline tests | `baseline-tests` | Same pinned target and suite manifest | `baseline_passed` | Check existing behavior before evaluating the hypothesis. |
| Revocation comparison | `revocation` | Approved fork block; correct delegated-account setup; valid owner/signature; relevant revocation action | `valid_pre_revocation_signature`, `same_digest_and_signature`, `post_revocation_erc1271_accepts_same_signature` | Test the invariant using identical digest and signature across the revocation boundary. |
| Patched negative control | `patched-negative-control` | Separately reviewed patch or a sound harness-level control that changes only the relevant behavior | `post_revocation_signature_rejected_by_patch` | Establish that the exploit assertion fails when the suspected cause is removed. |
| Optional downstream Permit2 | `permit2-fork` | Only if in scope; verify allowance, signature/permit, token, spender, and balance prerequisites | `permit2_prerequisites_verified`, `balance_delta_measured` | Verify downstream impact with exact pre/post balances; do not infer impact from ERC-1271 behavior alone. |

`revocation` and `permit2-fork` currently require the `fork-test` method in the registry; `patched-negative-control` and `baseline-tests` require `local-test`. Do not run a profile unless the registered scope permits that method. A suite record currently maps to a reviewed-intent profile ID only; the actual command dispatcher is not implemented.

## Harness design notes

- Pin every comparison to one repository/commit, compiler config, chain ID, and explicit nonzero block. Never silently replace the selected block with `latest`.
- Record the proxy address, implementation address, runtime code hashes, implementation resolution path, and EIP-7702 delegation context before drawing conclusions.
- Define the precise ERC-1271 return-value expectation for the pinned target and distinguish revert, malformed return data, magic-value success, and explicit invalid-signature outcomes.
- Use the same digest and signature bytes before/after revocation. Record the account and relevant state values with each observation.
- Include tests for an unrelated invalid signature, an unauthorized owner, and the unchanged valid pre-revocation baseline.
- Keep the positive reproduction independent from the patched negative control. The control must be semantically justified; merely changing a test expectation is not a valid patch control.
- If symbolic analysis is not suitable for this behavior, document why G7 is inapplicable under an approved policy basis rather than manufacturing a symbolic proof.
- If using multiple RPC providers, query the same chain ID and exact block and compare a documented normalized state/code digest. Provider disagreement means inconclusive pending investigation.

## Evidence artifacts to collect

1. Authorized target/scope manifest and source tree manifest.
2. Exact repository URL, full commit SHA, source file excerpts/line references, compiler settings, dependency lockfile, and tool/container versions.
3. Test harness source and its hash.
4. Raw command logs, Foundry traces, assertion result JSON, test seed if any, and resource/timeout information.
5. Runtime/delegation/implementation observations and code hashes at the pinned state.
6. Before/after state values, identical digest/signature identifiers (do not disclose private keys), ERC-1271 return bytes, and negative-control output.
7. If Permit2 is tested, exact allowance/permit prerequisites and pre/post token balances with arithmetic showing the delta.
8. Runner-signed receipt bound to run ID, suite profile, exact source commit, chain, block, and SHA-256 hashes of the actual stored bytes.
9. Known-issue/overlap sources actually reviewed, severity rubric version, independent review decision, and limitations.

Do not add secrets, private keys, seed phrases, or production credentials to artifacts. Use test-only keys inside a disposable worker.

## Readiness decisions

- A test process exit code of zero is not a vulnerability verdict.
- A receipt is accepted only when identity, HMAC, source/scope binding, required assertions, and actual artifact bytes pass deterministic validation.
- `execution_status`, `finding_status`, `review_status`, `approval_status`, and `submission_status` remain independent.
- The human finding decision may become `supported` only after the required G1–G8 gates and verified evidence qualify. Independent review (G9) and human submission authorization (G10) are separate later decisions.
- A negative, conflicting, or incomplete observation must remain rejected/inconclusive as appropriate; the model must not rewrite it as success.
- No Cantina report is submitted by this implementation. The report endpoint can only prepare a local draft and record authorization after the gates pass.

## Current completion state

The project contains a queue-only suite registry, typed receipt shape, HMAC verifier, content-addressed artifact verification, a 49-agent registry, and offline policy/evidence checks. Source-manifest upload alone cannot pass G1; this was intentionally made inconclusive so repository authenticity and source-line provenance cannot be bypassed. It does **not** contain the actual test contracts/harness, remote runner, RPC gateway, full database-backed integration test, or a verified target manifest. Therefore this plan has not reproduced or disproved Finding #1736.
