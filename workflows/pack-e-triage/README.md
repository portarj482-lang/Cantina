# Pack E Triage: Hallucination & Citation Dropper Workflow

## Purpose and Scope

`workflow-hallucination-dropper.sh` verifies candidate citations in security reports against a pinned Git commit. It prevents hallucinated line references, phantom files, and misattributed snippets from polluting vulnerability triage packages and finding envelopes.

It operates strictly on the active repository at an immutable commit hash (defaulting to `HEAD^{commit}`) and emits two cryptographically traceable, schema-validated artifacts into `bounties/<SLUG>/scans/`:
1. `hallucination_audit.json` — Detailed citation verification outcomes, unverified citations, invalid records, and skip rationales.
2. `hallucination_audit.provenance.json` — Operational provenance manifest detailing scanned files, commit identity, execution timestamp, and error records.

---

## Environment and Dependency Requirements

- **Operating System:** Linux (POSIX-compliant shell environment)
- **Dependencies:**
  - `bash` (v4.0+)
  - `git` (v2.20+)
  - `python3` (v3.10+)
  - `jsonschema` (v4.0+, optional for offline schema validation)

---

## CLI Syntax and Examples

### Synopsis

```bash
./workflow-hallucination-dropper.sh --slug SLUG [OPTIONS]
```

### Options

| Flag | Description | Default |
|---|---|---|
| `--slug SLUG` | **Required.** Bounty slug matching `^[A-Za-z0-9][A-Za-z0-9_-]{0,99}$` | None |
| `--sources GLOB[,GLOB...]` | Comma-separated list of repository-relative report globs | `bounties/<slug>/findings/*.md,bounties/<slug>/reports/*.md,bounties/<slug>/*.md` |
| `--adapter MODULE` | Pluggable Python module or filepath implementing citation extraction | `adapters.example_adapter` |
| `--commit COMMIT_ID` | Pinned Git commit hash to audit against | `git rev-parse HEAD^{commit}` |
| `--dry-run` | Read-only preview mode (default behavior) | `true` (if `--confirm` omitted) |
| `--confirm` | Authorize output artifact creation and durable atomic replacement | `false` |
| `-h`, `--help` | Show usage documentation | None |

### Examples

#### 1. Dry-Run / Preview (Default)
Audits citations without writing any files to disk. Returns `0` on valid execution:
```bash
./workflows/pack-e-triage/workflow-hallucination-dropper.sh --slug base --dry-run
```

#### 2. Confirmed Execution
Audits citations and writes `hallucination_audit.json` and `hallucination_audit.provenance.json` atomically:
```bash
./workflows/pack-e-triage/workflow-hallucination-dropper.sh --slug base --confirm
```

#### 3. Custom Report Source Globs
```bash
./workflows/pack-e-triage/workflow-hallucination-dropper.sh \
  --slug base \
  --sources "bounties/base/hypotheses/*.md,bounties/base/findings/*.md" \
  --confirm
```

#### 4. Custom Adapter Invocation
```bash
./workflows/pack-e-triage/workflow-hallucination-dropper.sh \
  --slug base \
  --adapter workflows/pack-e-triage/adapters/example_adapter.py \
  --confirm
```

---

## Preview and Confirmation Semantics

- **Default behavior:** If `--confirm` is not passed, preview mode is enabled by default.
- **Preview guarantees:** Strictly read-only. No files or directories are created, modified, or removed in `scans/`.
- **Conflicting flags:** Specifying both `--dry-run` and `--confirm` is rejected immediately with exit code `4`.
- **Preview exit code:** A valid preview returns exit code `0` even when candidate citations fail verification (failures are reported to `stderr`).
- **Sentinel guarantee:** The success sentinel `ALL_CITATIONS_VERIFIED` is **never** emitted during a preview run.

---

## Pluggable Report Adapter Contract

Adapters extract citation candidates from raw report files. An adapter does not judge citation correctness; the core verification engine evaluates candidate citations against the Git tree.

### Interface

```python
def extract_citations(report_path: str) -> list[dict]:
    """Extract normalized citation candidates from one report file."""
```

### Normalized Record Schema

Each item returned by `extract_citations` must be a dictionary conforming to:

```json
{
  "target": "repository-relative/path.sol",
  "start_line": 10,
  "end_line": 14,
  "reported_in": "bounties/base/findings/F-001.md"
}
```

### Validation Invariants

- `target`: Non-empty string. Absolute paths (`/etc/...`) and path traversal (`../...`) are rejected.
- `start_line`: Positive integer (`>= 1`). Booleans are explicitly rejected.
- `end_line`: Integer `>= start_line`. Booleans are explicitly rejected.
- `reported_in`: Non-empty string indicating originating report file.

---

## Exit Codes

| Code | Meaning | Operational Action |
|---|---|---|
| `0` | Verification succeeded, or valid preview completed | Confirmed run emitted `ALL_CITATIONS_VERIFIED`; preview emitted summary to `stderr`. |
| `1` | Citations unverified, flagged, or zero citations found | Review `unverified_citations`, `invalid_citations`, or `errors` in `hallucination_audit.json`. |
| `2` | Output creation, synchronization, or replacement failed | Check directory permissions, symlink restrictions, and filesystem mounts. |
| `3` | Required dependency missing | Install missing tool (`git` or `python3`). |
| `4` | Invalid CLI arguments, slug violation, traversal, or conflicting options | Review CLI flags against usage instructions. |

---

## Security Invariants & Robustness Guarantees

1. **Path Containment:** The workflow enforces strict path containment. Any slug containing path traversal (`..`), slashes, or special characters is rejected with exit code `4` before filesystem checks occur.
2. **Sources & Adapter Traversal Gating:** `--sources` and `--adapter` reject external absolute paths and traversal patterns (`..`) with exit code `4`.
3. **Symlink Directory Protection:** If `scans/`, the bounty directory, or any path component is a symbolic link, execution aborts with exit code `2`.
4. **Cross-Device Protection:** Writes are refused if the output directory is located on a different filesystem device than the Git repository root (`st_dev` check).
5. **Atomic Durability:** Files are written to temporary files on the same filesystem device, flushed, synced via `os.fsync`, set with restrictive `0600` permissions, and atomically replaced via `os.replace`. The containing directory is subsequently fsynced.
6. **Git Tree Integrity:** Files are verified against Git blob objects at the pinned revision using `git ls-tree -z` and `git cat-file blob`.
7. **Bounded Object Processing:** Blobs exceeding 10MB are bounded via `git cat-file -s` and safely skipped (`BLOB_SIZE_EXCEEDED`). Blobs are cached by SHA to eliminate redundant subprocess execution.
8. **Git Submodules & Symlinks:** Repository symlinks (`mode 120000`) and git submodules (`mode 160000` / `commit`) are explicitly flagged as `SYMLINK_TARGET` and `SUBMODULE_TARGET`.
9. **Zero-Citation Sentinel Guard:** The sentinel `ALL_CITATIONS_VERIFIED` is strictly emitted only when `citations_audited > 0` and `dropped_count == 0` on a confirmed run. If no citations are found, status is set to `NO_CITATIONS_FOUND` and exit code `1` is returned.
10. **Structured JSON Lines Logging:** All operational logs and errors across both Bash and Python emit structured JSON Lines to `stderr`.

---

## CI Invocation & Acceptance Checklist

Run the automated test suite in continuous integration:

```bash
./workflows/pack-e-triage/tests/test_workflow_hallucination_dropper.sh
```

Schema validation check:

```bash
python3 workflows/pack-e-triage/validate_schemas.py --dir bounties/<SLUG>/scans
```

- [x] **Syntax Check**: `bash -n workflows/pack-e-triage/workflow-hallucination-dropper.sh` passes without syntax errors.
- [x] **Dependency Check**: Returns exit code `3` when `git` or `python3` is missing.
- [x] **Argument Validation**: Missing `--slug`, unknown options, traversal in `--sources`, traversal in `--adapter`, and conflicting duplicate options return exit code `4`.
- [x] **Slug Security**: Slugs containing traversal or exceeding 100 characters return exit code `4` without creating directories.
- [x] **Path & Symlink Safety**: Rejects symlinked `scans/` and symlinked bounty directories with exit code `2`.
- [x] **Cross-Device Safety**: Output locations on differing filesystem devices abort with exit code `2`.
- [x] **Preview Isolation**: Preview mode writes zero files to disk and returns exit code `0`.
- [x] **Git NUL-Delimited Parsing**: Filenames containing spaces, quotes, and tabs match correctly without corruption.
- [x] **Blob Safety & Bounding**: Empty blobs, binary blobs, and blobs > 10MB are safely handled and flagged without crashes.
- [x] **Submodule Explicit Handling**: Submodules are identified and flagged as `SUBMODULE_TARGET`.
- [x] **Adapter Validation**: Candidate citations containing boolean line numbers or path traversal targets are rejected.
- [x] **Atomic Durability**: Writes use temporary files on the same filesystem device with `os.fsync`, `0600` permissions, `os.replace`, and directory syncing.
- [x] **Sentinel Integrity**: `ALL_CITATIONS_VERIFIED` is output to `stdout` strictly upon non-empty, 100% verification and confirmed writes. Zero-citation runs do not emit the sentinel.
- [x] **Schema Validation**: Both `hallucination_audit.json` and `hallucination_audit.provenance.json` conform to Draft 2020-12 JSON schemas.
- [x] **Monorepo Hygiene**: `make audit` passes with zero tracked transient files.
