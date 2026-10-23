# Lifecycle Mapping Matrix: Glassbox Mirror Plane to Dynamic Fuzzing Verification

This matrix defines the mapping between the 8 stages of the Glassbox Mirror Plane Orchestration protocol and the concrete runtime execution phases of the Echidna and Medusa dynamic fuzzing pipelines.

| Glassbox Stage | Dynamic Fuzzing Phase | Primary Specialist / Role | Inputs & Evidence | Validated Contract / Schema | Gate & Sync Barrier |
|---|---|---|---|---|---|
| **Stage 1 — Perception Filtering** | Ingestion & Scope Containment | Filesystem Security Specialist | `--slug`, `--target`, `--output-dir`, repo root | `StageResult`, Canonical path containment checks | `SandboxContainmentGate`: Rejects symlink escapes & target source overwrites |
| **Stage 2 — Parsing & Tokenization** | Project & Config AST Parsing | Repository Investigator | Target `.sol` files, `medusa.json` / `echidna.yaml` | `StageResult`, `config_sha256` | `TargetHarnessGate`: Rejects empty target directories without Solidity sources or tool configuration |
| **Stage 3 — Structural Feature Interpretation** | Invariant Discovery & AST Extraction | Solidity Specialist | Parsed AST, `property_*`, `crytic_*`, `echidna_*` | `StageResult`, Discovered invariants list | Syntax validation; records public entrypoints and state variables |
| **Stage 4 — Thinking & Planning** | Task Formulation & Resource Limits | Fuzzing Engineer | Parameters: seed, test-limit, timeout, workers | `TaskContract` (`task_contract.schema.json`) | Validates task schema; maps CLI options against installed binary |
| **Stage 5 — Reasoning & Verification** | Fuzzing Campaign Sandbox Execution | Fuzzing Engineer | Tool binary, target, bounded timeout, reviewed command | `stdout.log`, `stderr.log`, `receipt.json` | `AuthorizationGate`: Checks `--confirm && !--dry-run`. Subprocess bounded by timeout |
| **Stage 6 — Context & Scope Modeling** | Provenance & Digest Pinning | Context Specialist | Git revision, solc version, source hashes, binary digest | `StageResult`, `source_digest` | Binds run to immutable repository commit hash |
| **Stage 7 — Awareness & Semantic Interpretation** | Challenger & Counterexample Extraction | Independent Challenger | Fuzzer stdout (JSON/text), call sequences, traces | `FindingContract` (`finding_contract.schema.json`) | Parses passing/falsified properties; extracts transaction traces |
| **Stage 8 — Meta-Governance & Authorization** | Gate Adjudication & Atomic Swap | Governance Auditor | Complete evidence package, manifest, receipt | `CampaignManifest`, `EvidenceEnvelope`, `GateDecisionContract` | `CampaignOutcomeGate`: Reconciles exit codes, enforces atomic file swap via `os.replace` |

---

## Synchronization Barrier Protocol

At each transition barrier between stages:
1. **Schema Validation:** Intermediate data structures must validate against their defined JSON schema before proceeding.
2. **Digest Verification:** Payloads must have their cryptographic SHA-256 computed and matched.
3. **Fail-Closed Gate Checks:** Any failed gate immediately halts execution and issues an auditor veto (`VETOED`), preventing unverified findings from being promoted.
4. **Atomic Publication:** Physical disk writes only execute at Stage 8 via temporary file replacement (`.tmp.<pid>` -> target file), ensuring that failed runs never leave partial or corrupt artifacts.
