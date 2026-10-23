# Execution Security & Runtime Containment Specification

**Version:** 1.0.0  
**Status:** Canonical Reference  
**Applicability:** Dynamic Analysis, Verification Workflows, Foundry Adapters (Pack C)

---

## 1. Principles of Runtime Enforcement

In the Glassbox Mirror Plane architecture, prompt governance defines intended agent behavior, but runtime isolation strictly enforces execution safety. Neither agent agreement nor a successful subprocess exit code is accepted as proof of security without runtime containment.

Key security invariants:
1. **No Authorization by Implication:** The `--confirm` flag requests live execution; runtime policy independently decides whether live execution is authorized.
2. **Fail-Closed Default:** In the absence of an explicit `--confirm` flag, or when `--dry-run` is present, the system defaults to safe preview mode.
3. **Mutual Exclusivity:** The orchestration entry points strictly reject combining `--dry-run` and `--confirm`.
4. **Defense-in-Depth Path Containment:** Both the shell orchestration wrapper and the Python execution adapter independently verify that all target and output directory paths are strictly contained within `REPO_ROOT`.
5. **Leaf Symlink Safety:** Traversal sequences (`..`), absolute paths, and symlinks (both intermediate and leaf/final component) pointing outside `REPO_ROOT` are rejected prior to any execution.
6. **Atomic Artifact Serialization:** All receipts, logs, and findings are serialized via atomic temporary files (`.tmp.<pid>`), flushed to disk with `os.fsync`, and replaced with `os.replace`.

---

## 2. Path Containment Specification

### Orchestration Boundary (Shell Wrapper)
The shell wrapper canonicalizes target and output paths using Python `pathlib.Path`:
- Absolute paths are forbidden; inputs must be repository-relative.
- The path is resolved against `REPO_ROOT` using `.resolve(strict=False)`.
- The resolved path must satisfy `path.is_relative_to(root)`.
- Leaf symlinks pointing outside `REPO_ROOT` are resolved and detected.
- Target directories must exist and be valid directories (`target.is_dir()`).
- Output paths, if already existing, must be directories (`output.is_dir()`).

### Adapter Boundary (Python Subprocess)
The backend adapter (`foundry_adapter.py`) independently resolves `REPO_ROOT` and verifies:
```python
target_path = Path(args.target).resolve()
if not target_path.is_relative_to(repo_root):
    sys.exit(1)
```
This ensures that even if an execution bypasses the shell wrapper, the adapter prevents unauthorized directory access or arbitrary file overwrites.

---

## 3. Sandbox Lifecycle

1. **Epoch Initialization:** Setup isolated output directories beneath the authorized target scan path (`bounties/<target>/scans/fuzz`).
2. **Bounded Execution:** Subprocesses run with strict timeouts (e.g. 120s) and captured standard streams (`stdout`, `stderr`).
3. **Digest Pinning:** Every output artifact (`stdout.log`, `stderr.log`, `forge_output.txt`) has its SHA-256 digest computed immediately upon subprocess termination.
4. **Atomic Emission:** `receipt.json` records tool version, command template, exit code, duration, timestamps, and artifact SHA-256 digests.
5. **Receipt Verification:** Execution receipts are read back and validated against schemas before being promoted to stage results.
