# Pack B — Static Analysis & SARIF Collector Workflow

## Universal Oracle–Orchestrator Meta-Agent (UOOMA) Profile

**Workflow Profile:** `UOOMA-PACK-B`  
**Architecture:** UAIA v1.0.0  
**Specification Document:** [META_PERSONA.md](./META_PERSONA.md)  
**Lifecycle Mapping Matrix:** [LIFECYCLE_MAPPING.md](./LIFECYCLE_MAPPING.md)  
**Canonical Output:** `bounties/<slug>/scans/normalized_sarif.json`  
**Integrity Receipt:** `bounties/<slug>/scans/receipt.json`  
**Schema Definition:** [normalized_sarif.schema.json](./schemas/normalized_sarif.schema.json)  

---

## 1. Architecture Overview

The Pack B SARIF Collector workflow transforms heterogeneous static analysis scan results (Slither JSON, Aderyn JSON, Semgrep JSON, and generic SARIF v2.1.0) into a single, standardized, schema-validated SARIF artifact and an accompanying cryptographic integrity receipt.

### 7-Layer UOOMA Hierarchy
1. **Layer 1 — Oracle and Policy Gate:** Establishes empty result policy, validates evidence standards, and governs admission decisions.
2. **Layer 2 — Orchestrator & Task Management:** Coordinates lifecycle stage progression, dependency tracking, and bounded retries.
3. **Layer 3 — Specialist Execution:**
   - *Filesystem Security Agent:* Enforces strict path containment (`Path.is_relative_to`), prevents symlink escapes, and verifies read-only discovery.
   - *SARIF Processing Agent:* Normalizes heterogeneous scan outputs into canonical SARIF v2.1.0 runs and applies versioned deduplication.
   - *JSON & Schema Agent:* Validates inputs and serializes outputs according to `normalized_sarif.schema.json`.
4. **Layer 4 — Testing & Verification:** Executes unit, integration, and regression suites against boundary test fixtures.
5. **Layer 5 — Independent Challenger:** Executes adversarial negative controls, path traversal attempts, and simulated failure recovery checks.
6. **Layer 6 — Admission & Release Control:** Evaluates whether status reaches `COLLECTED`, `EMPTY`, `PARTIAL`, or `FAILED` and authorizes atomic swap.
7. **Layer 7 — Audit, Observability & Learning:** Computes exact-byte SHA-256 disk digests, verifies read-back integrity, and writes `receipt.json`.

### Glassbox Mirror Plane 8-Stage Mapping
The 8-stage Glassbox perception pipeline synchronizes seamlessly with the 14-stage SARIF collection lifecycle:
1. **Perception:** Scan directory discovery & target slug parameter ingestion.
2. **Parsing:** Multi-format syntax validation (Slither, Aderyn, Semgrep, SARIF v2.1.0).
3. **Interpretation:** Tool status verification against `global/tooling.md` and semantic extraction.
4. **Planning:** Deduplication key construction (`ruleId:uri:startLine:message_hash`).
5. **Reasoning:** Invariant evaluation (`WRITE_ALLOWED = CONFIRM && !DRY_RUN`).
6. **Context:** Provenance assembly, rejected input cataloging, and metadata binding.
7. **Awareness:** Atomic staging to `.tmp.<pid>` and pre-swap read-back syntax validation.
8. **Governance:** Atomic swap (`os.replace`), exact-byte digest computation, and receipt generation.

---

## 2. Operating Modes

The engine provides five distinct execution modes to adhere strictly to least-privilege operations:

| Mode | Allowed Mutations | Description |
|---|---|---|
| `INSPECT` | **None** (Read-Only) | Discovers and reports scan files in `bounties/<slug>/scans` without normalization or file modification. |
| `PLAN` | **None** (Read-Only) | Discovers, parses, normalizes, and reports projected findings breakdown with status `PLANNED`. |
| `DRY_RUN` | **None** (Read-Only) | Simulates full workflow, validates schema, and reports dry-run preview. Never writes to disk. |
| `EXECUTE` | **Atomic Write** (when confirmed) | Standard execution. Requires `--confirm` (and not `--dry-run`) to publish `normalized_sarif.json` and `receipt.json`. |
| `VERIFY` | **None** (Read-Only) | Validates existing `normalized_sarif.json` against canonical schema, verifies `receipt.json`, and asserts exact-byte hash matches disk bytes. |

---

## 3. CLI Usage

### Hardened Shell Orchestrator
```bash
./workflow-sarif-collector.sh [--mode MODE] [--slug SLUG] [--dry-run] [--confirm] [--empty-allowed] [--fail-sim] [--corrupt-sim]
```

### Python Engine Direct Invocation
```bash
python3 sarif_collector.py [--mode MODE] [--slug SLUG] [--dry-run] [--confirm] [--empty-allowed] [--fail-sim] [--corrupt-sim] [--target-dir DIR]
```

### Command Flags
- `--mode MODE`: Operating mode: `INSPECT`, `PLAN`, `DRY_RUN`, `EXECUTE`, `VERIFY` (default: `EXECUTE`).
- `--slug SLUG`: Target bounty workspace under `bounties/` (default: `base`). Must strictly match `^[A-Za-z0-9][A-Za-z0-9_-]*$`.
- `--dry-run`: Preview collection plan without modifying any files (takes precedence over `--confirm`).
- `--confirm`: Authorize atomic write and publication to `bounties/<slug>/scans/normalized_sarif.json`.
- `--empty-allowed`: Permit scan directories containing zero findings without error.
- `--fail-sim`: Simulate execution failure for rollback and negative control testing.
- `--corrupt-sim`: Simulate corrupted JSON write to verify atomic swap safety.
- `--target-dir DIR`: Explicit directory override (must be strictly contained within the repository root).

---

## 4. Exit Codes

- `0`: Success (including verified dry-run preview, valid empty collection, and successful artifact verification).
- `1`: Execution, validation, normalization, or verification error.
- `2`: Bad argument, invalid slug, or path traversal violation.
- `3`: Missing target bounty directory or unresolvable scope.

---

## 5. Invariants & Security Boundaries

1. **Atomic File Swap:** All writes occur to `.tmp.<pid>` before renaming via `os.replace`. Existing valid artifacts survive interrupted or failed runs untouched.
2. **Fail-Closed Execution Gate:** `--dry-run` always overrides `--confirm`. Zero filesystem modifications occur during dry-run.
3. **Strict Path Containment:** Traversal attempts (`../`, absolute paths, symlinks escaping the repository root, forbidden characters) are rejected immediately (exit code 2).
4. **Two-Tier Digest Integrity:**
   - Canonical payload hash (`payload_sha256`) is embedded inside `normalized_sarif.json`.
   - Exact-byte file hash (`exact_file_sha256`) is computed from disk bytes post-swap and preserved in `receipt.json`.
5. **Deterministic Deduplication:** Finding identity is keyed on `ruleId:uri:startLine:message_hash` to ensure idempotent, repeatable collections.

---

## 6. Recovery & Rollback Procedures

- **Interrupted Run:** Temporary files are named `.tmp.*.<pid>.json`. On failure, the collector unlinks its PID-scoped temp file; existing published artifacts remain active.
- **Corrupted Input:** Any malformed scanner JSON is safely logged under `provenance.rejected_inputs` and does not halt the collection of valid scan files.
- **Verification Failure:** Running `--mode VERIFY` detects any disk-level file tampering or schema deviation, reporting specific discrepancies and exiting with code 1.

---

## 7. Aderyn Static Analysis Workflow (SAMA / OAM)

**Capability:** SAMA (Security Analysis Meta-Agent)  
**Architecture:** OAM (Oracle Agentic Mesh)  
**Specification Document:** [REFACTORING_SAMA_OAM.md](./REFACTORING_SAMA_OAM.md)  
**Canonical Output:** `bounties/<slug>/scans/aderyn/evidence_envelope.json`  
**Schema Definition:** [evidence_envelope.schema.json](./schemas/evidence_envelope.schema.json)  

### CLI Usage
```bash
./workflow-aderyn.sh [--slug SLUG] [--target TARGET] [--output-dir DIR] [--dry-run] [--confirm] [--timeout SECONDS]
```

### Invariants & Guarantees
- **Authorization Precedes Execution:** `--dry-run` takes precedence over `--confirm`; execution requires fresh preflight checks and tool status `OK` in `global/tooling.md`.
- **Preserved Adapter Failure Semantics:** Nonzero scanner exit codes are propagated directly and recorded in execution receipts.
- **Independent Evidence Validation:** Artifact SHA-256 digests, schema compliance, and target attribution are verified independently of adapter success messages.
- **Standard Evidence Envelope:** Published atomically with monotonic lifecycle state transitions.

