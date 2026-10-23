# Universal Adaptive Engineering & Safety Rules

## 1. Authority Hierarchy
1. Applicable law, system isolation, and non-destructive safety constraints.
2. Platform execution policy: Ground Rule #2 (No live funds, fork-only execution, zero broadcast transactions).
3. Workspace invariants and approved scope manifests (`scope.md`).
4. Canonical contracts and adapter boundaries (`ArchitectureAdapter`).
5. Task criteria and evidence standards.

## 2. Evidence-Based Verification Standard
- Never claim an invariant, contract, tool, or fix is verified without reproducible evidence.
- A passing test proves behavior only under tested parameters; it is not universal proof.
- Checklists and static AST scans without executed test suites must report `COMPLETED_WITH_LIMITATIONS`.
- Negative controls and adversarial falsification checks are mandatory for all critical invariant evaluations.

## 3. Path Containment & Least Privilege
- All filesystem operations are bounded by `target_context.target_root` or `workspace_root`.
- Strict path containment (`Path.is_relative_to`) must be enforced on all inputs.
- Cross-target scope contamination is strictly prohibited. Standalone targets outside `bounties/` must evaluate without inheriting alien bounty scopes.

## 4. Monorepo Hygiene & Nested Repository Invariants
- Never commit loose `.git` directories or unmanaged nested repositories into the workspace.
- Repositories > 50MB must be tracked via `.gitmodules` as canonical Git submodules.
- Submodule names in `.gitmodules` must use path-derived prefixes to eliminate section collisions.
- First-party packages < 5MB absorbed into the monorepo must have their historical `.git` metadata preserved in `maintenance/backups/<timestamp>/`.
- Tracked runtime files (`.env`, `node_modules/`, `*.so`, `__pycache__`, `*.log`) are strictly prohibited; `make audit` must pass before any release commit.
- External API transports must enforce strict TLS verification and reject HTTP redirects (allow_redirects=False).

## 5. Security Scan & Triage Invariants (Pack E)
- Strictly separate agent definitions, workflow implementations, and execution results.
- Never declare a vulnerability triage workflow `COMPLETE` unless candidate evidence has been discovered and evaluated.
- An empty candidate set must report zero candidates with status `TRIAGE_INCOMPLETE` or `TRIAGE_COMPLETE_WITH_LIMITATIONS`.
- Triage artifacts must retain independent severity (impact) and confidence (evidentiary certainty) fields.
- Target slug inputs must enforce strict path traversal validation (`^[A-Za-z0-9][A-Za-z0-9_-]*$`) and canonical workspace containment.
- Artifact serialization must be atomic (via temporary file swap) and generated using standard JSON serializers.

## 6. Smart Contract Attack-Surface & Pathway Reconnaissance Invariants (Pack A)
- Security reconnaissance agents (Pack A) must never report `entrypoints_mapped: true` or `PATHWAYS_SCOUTED` status without verified source evidence.
- Reconnaissance completion markers (`completion.complete`) must be derived from actual evaluated source ASTs and execution paths, never assumed from a successful shell wrapper exit.
- `WRITE_ALLOWED = CONFIRM && !DRY_RUN` gate is mandatory; `--dry-run` must always override `--confirm`.
- Reconnaissance orchestrators must exit 3 (`BLOCKED`) when prerequisites or in-scope sources are missing, and exit 4 (`PARTIAL`) when coverage criteria are not met.
- Cross-contract call edges and state transitions must distinguish `verified`, `inferred`, `unverified`, and `blocked` evidence states.

## 7. Static Analysis & SARIF Collector Invariants (Pack B)
- Never report `status: "COLLECTED"` without verified source scan evidence and schema-compliant normalized SARIF output.
- An empty scan directory must report status `EMPTY` only when explicitly permitted by Oracle policy; otherwise report `COLLECTED_WITH_LIMITATIONS` or `FAILED`.
- Multi-tool inputs (Slither, Aderyn, Semgrep, raw SARIF) must preserve individual tool provenance, rule identifiers, and physical source locations.
- Deduplication must follow a deterministic, versioned identity policy (`ruleId:path:line:message_hash`); dropped duplicates must be accounted for in summary statistics.
- `--dry-run` must always override `--confirm`; zero filesystem writes are permitted during dry-run execution.
- Artifact serialization to `bounties/<slug>/scans/normalized_sarif.json` must be atomic via temporary file swap and verified by read-back digest.
- Existing valid artifacts must survive failed or interrupted publication runs completely intact.

## 8. Dynamic Analysis & Test Execution Invariants (Pack C)
- Workflow shell scripts must enforce `set -Eeuo pipefail` and `IFS=$'\n\t'`.
- All CLI argument parsers must fail closed: unknown flags and missing option values must abort execution immediately with exit code 1 or 2.
- `--dry-run` must always override `--confirm`. Confirmed execution requires explicit authorization and passes policy checks.
- Path containment in wrappers must verify both the parent directory and the final path component against symlink escapes outside `REPO_ROOT`.
- Python adapters must independently verify path containment using `Path.is_relative_to` or canonical resolution rather than blindly trusting shell wrappers.
- All artifact serialization (receipts, manifests, findings) must be atomic via temporary file swap and `os.fsync`.
- Process exit code 0 establishes only what tests passed under recorded conditions; it is not universal proof of security.
