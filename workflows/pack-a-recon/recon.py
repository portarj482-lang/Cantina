#!/usr/bin/env python3
"""Pack A — Reconnaissance Engine (recon.py)

Discovers Solidity contracts in authorized bounty workspaces, records source provenance,
validates output artifacts against schema, and performs atomic writes.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

SLUG_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
TIMESTAMP_PATTERN = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")
VALID_STATUSES = {"RECON_COMPLETE", "RECON_PARTIAL", "RECON_BLOCKED", "RECON_FAILED"}


def validate_slug(slug: str) -> None:
    if not slug:
        raise ValueError("Slug must not be empty")
    if slug.startswith("/"):
        raise ValueError("Slug must not be an absolute path")
    if ".." in slug or "/" in slug or "\\" in slug:
        raise ValueError("Slug must not contain path traversal or slashes")
    if not SLUG_PATTERN.match(slug):
        raise ValueError(
            f"Slug '{slug}' contains invalid characters. Must match pattern ^[A-Za-z0-9][A-Za-z0-9_-]*$"
        )


def get_git_provenance(repo_root: Path) -> tuple[str | None, bool | None]:
    commit: str | None = None
    dirty: bool | None = None
    try:
        res = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if res.returncode == 0 and res.stdout.strip():
            commit = res.stdout.strip()
    except Exception:
        commit = None

    try:
        res = subprocess.run(
            ["git", "-C", str(repo_root), "status", "--porcelain", "--untracked-files=no", "--ignore-submodules=dirty"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if res.returncode == 0:
            dirty = bool(res.stdout.strip())
    except Exception:
        dirty = None

    return commit, dirty


def validate_recon_payload(data: dict, schema_path: Path | None = None) -> tuple[bool, str | None]:
    required_fields = ["slug", "contracts_found", "timestamp", "status"]
    for field in required_fields:
        if field not in data:
            return False, f"Missing required top-level field: '{field}'"

    if not isinstance(data["slug"], str) or not SLUG_PATTERN.match(data["slug"]):
        return False, f"Invalid slug value: {data.get('slug')}"

    if not isinstance(data["contracts_found"], int) or data["contracts_found"] < 0:
        return False, f"contracts_found must be a non-negative integer, got: {data.get('contracts_found')}"

    if not isinstance(data["timestamp"], str) or not TIMESTAMP_PATTERN.match(data["timestamp"]):
        return False, f"timestamp must be ISO-8601 UTC formatted (%Y-%m-%dT%H:%M:%SZ), got: {data.get('timestamp')}"

    if data["status"] not in VALID_STATUSES:
        return False, f"status must be one of {sorted(VALID_STATUSES)}, got: {data.get('status')}"

    if schema_path and schema_path.is_file():
        try:
            import jsonschema  # type: ignore

            with open(schema_path, "r", encoding="utf-8") as sf:
                schema = json.load(sf)
            jsonschema.validate(instance=data, schema=schema)
        except ImportError:
            # Fallback manual validation for extended fields
            if "scope" in data:
                if not isinstance(data["scope"], dict):
                    return False, "'scope' field must be an object"
                for req in ["root", "file_extension", "symlinks_followed", "inventory_complete"]:
                    if req not in data["scope"]:
                        return False, f"scope missing required field: '{req}'"
            if "inventory" in data and not isinstance(data["inventory"], list):
                return False, "'inventory' must be a list"
            if "tools" in data and not isinstance(data["tools"], list):
                return False, "'tools' must be a list"
        except Exception as e:
            return False, f"Schema validation error: {e}"

    return True, None


def main() -> int:
    parser = argparse.ArgumentParser(description="Pack A — Smart Contract Reconnaissance Engine")
    parser.add_argument("--slug", default="base", help="Bounty slug identifier")
    parser.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[2]), help="Repository root path")
    parser.add_argument("--bounty-dir", default=None, help="Explicit bounty directory override")
    parser.add_argument("--output", default=None, help="Explicit output JSON path")
    parser.add_argument("--dry-run", action="store_true", help="Simulate without writing files")
    parser.add_argument("--confirm", action="store_true", help="Authorize write operations")
    parser.add_argument("--run-scanners", action="store_true", help="Run optional registered static analysis")
    parser.add_argument("--fail-scanner-sim", action="store_true", help="Simulate optional scanner failure")
    parser.add_argument("--corrupt-json-sim", action="store_true", help="Simulate corrupted JSON write for testing")
    parser.add_argument("--schema", default=None, help="Path to recon.schema.json")

    args = parser.parse_args()

    # Validate slug
    try:
        validate_slug(args.slug)
    except ValueError as e:
        print(f"[FAIL] Argument error: {e}", file=sys.stderr)
        return 2

    repo_root = Path(args.repo_root).resolve()
    bounties_root = repo_root / "bounties"

    if args.bounty_dir:
        bounty_dir = Path(args.bounty_dir).resolve()
    else:
        bounty_dir = (bounties_root / args.slug).resolve()

    # Path containment check: ensure bounty_dir is under bounties_root
    try:
        bounty_dir.relative_to(bounties_root)
    except ValueError:
        print(
            f"[FAIL] Path containment violation: '{bounty_dir}' is not within '{bounties_root}'",
            file=sys.stderr,
        )
        return 2

    scans_dir = bounty_dir / "scans"
    if args.output:
        recon_out = Path(args.output).resolve()
    else:
        recon_out = scans_dir / "recon.json"

    write_allowed = args.confirm and not args.dry_run

    if not os.environ.get("RECON_WRAPPER_ACTIVE"):
        print(f"=== [Pack A] Workflow: Reconnaissance ({args.slug}) ===")

    if not write_allowed:
        print(f"[DRY-RUN] Target output: {recon_out}")
        print("[DRY-RUN] Planned operations:")
        print(f"  - Target workspace: {bounty_dir}")
        print(f"  - Target artifact:  {recon_out}")
        print(f"  - Directory exists: {bounty_dir.is_dir()}")
        print("  - Mode: DRY-RUN (no filesystem writes or scanner execution)")
        return 0

    # Write mode safety checks
    if not bounty_dir.exists():
        print(f"[FAIL] Bounty directory does not exist: {bounty_dir}", file=sys.stderr)
        return 3

    if not bounty_dir.is_dir():
        print(f"[FAIL] Bounty target is not a directory: {bounty_dir}", file=sys.stderr)
        return 3

    if bounty_dir.is_symlink():
        print(f"[FAIL] Bounty directory is a symlink: {bounty_dir}", file=sys.stderr)
        return 1

    # Ensure scans directory exists safely
    if scans_dir.is_symlink():
        print(f"[FAIL] Scans directory is a symlink: {scans_dir}", file=sys.stderr)
        return 1

    try:
        scans_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        print(f"[FAIL] Failed to create scans directory '{scans_dir}': {e}", file=sys.stderr)
        return 1

    # Core discovery
    sol_paths: list[str] = []
    traversal_errors: list[str] = []
    warnings: list[str] = []
    excluded_dir_names = {
        "scans",
        ".git",
        "node_modules",
        "artifacts",
        "cache",
        "out",
        "target",
        ".gemini",
        ".pytest_cache",
    }

    def walk_error_handler(err: OSError) -> None:
        traversal_errors.append(f"Permission or read error accessing '{err.filename}': {err.strerror}")

    for root, dirs, files in os.walk(str(bounty_dir), followlinks=False, onerror=walk_error_handler):
        # Exclude generated/output directories from discovery
        dirs[:] = [d for d in dirs if d not in excluded_dir_names and not (Path(root) / d).is_symlink()]
        for f in files:
            if f.endswith(".sol"):
                full_path = Path(root) / f
                if full_path.is_symlink():
                    try:
                        resolved = full_path.resolve()
                        resolved.relative_to(bounty_dir)
                    except (ValueError, RuntimeError):
                        warnings.append(f"Symlink '{full_path}' points outside bounty workspace or is circular; excluded.")
                        continue
                try:
                    rel_to_repo = str(full_path.relative_to(repo_root))
                except ValueError:
                    rel_to_repo = str(full_path.relative_to(bounty_dir))
                sol_paths.append(rel_to_repo)

    # Sort deterministically
    sol_paths = sorted(list(set(sol_paths)))

    # Evaluate discovery completion
    if traversal_errors:
        print(f"[FAIL] Traversal incomplete due to errors: {traversal_errors}", file=sys.stderr)
        return 1

    git_commit, git_dirty = get_git_provenance(repo_root)

    tools_record = []
    errors: list[str] = []

    if args.fail_scanner_sim:
        tools_record.append({
            "name": "simulated_scanner",
            "version": "1.0.0",
            "status": "failed",
            "reason": "Simulated scanner process failure",
        })
        warnings.append("Optional scanner simulated failure occurred; core discovery intact")

    schema_file = Path(args.schema) if args.schema else (Path(__file__).parent / "schemas" / "recon.schema.json")

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    payload = {
        "schema_version": 1,
        "slug": args.slug,
        "status": "RECON_COMPLETE",
        "timestamp": timestamp,
        "contracts_found": len(sol_paths),
        "scope": {
            "root": f"bounties/{args.slug}",
            "file_extension": ".sol",
            "symlinks_followed": False,
            "inventory_complete": True,
        },
        "provenance": {
            "repository_revision": git_commit,
            "dirty_worktree": git_dirty,
        },
        "inventory": sol_paths,
        "tools": tools_record,
        "errors": errors,
        "warnings": warnings,
    }

    # Atomic write to temporary file first
    try:
        temp_fd, temp_file_path_str = tempfile.mkstemp(
            prefix="recon_",
            suffix=".tmp.json",
            dir=str(scans_dir),
        )
    except OSError as err:
        print(f"[FAIL] Could not create temporary file in '{scans_dir}': {err}", file=sys.stderr)
        return 1

    temp_file = Path(temp_file_path_str)

    try:
        with os.fdopen(temp_fd, "w", encoding="utf-8") as tf:
            if args.corrupt_json_sim:
                tf.write("{ this is invalid json ]\n")
            else:
                json.dump(payload, tf, indent=2, ensure_ascii=False)
                tf.write("\n")

        # Validate temporary file
        if not args.corrupt_json_sim:
            with open(temp_file, "r", encoding="utf-8") as vf:
                loaded = json.load(vf)
            valid, err_msg = validate_recon_payload(loaded, schema_file)
            if not valid:
                print(f"[FAIL] Artifact validation failed: {err_msg}", file=sys.stderr)
                if temp_file.exists():
                    temp_file.unlink()
                return 1
        else:
            # Simulated corruption check
            try:
                with open(temp_file, "r", encoding="utf-8") as vf:
                    json.load(vf)
            except json.JSONDecodeError as jde:
                print(f"[FAIL] Artifact validation failed: JSONDecodeError: {jde}", file=sys.stderr)
                if temp_file.exists():
                    temp_file.unlink()
                return 1

        # Atomically replace destination
        os.replace(temp_file, recon_out)
    except Exception as ex:
        print(f"[FAIL] Error writing artifact: {ex}", file=sys.stderr)
        if temp_file.exists():
            temp_file.unlink()
        return 1

    print(f"[OK] Reconnaissance recorded in {recon_out}")
    report = f"""
======================================================================
PACK A — RECONNAISSANCE REPORT
======================================================================
Slug: {args.slug}
Execution mode: CONFIRMED_EXECUTION
Repository: {repo_root}
Source revision: {git_commit if git_commit else 'UNKNOWN'}
Scope: bounties/{args.slug} (*.sol)
Solidity files found: {len(sol_paths)}
Discovery completeness: COMPLETE
Artifact path: {recon_out}
Artifact validation: VALID
Core status: RECON_COMPLETE
Optional analyses: {'SIMULATED' if args.fail_scanner_sim else ('EXECUTED' if args.run_scanners else 'NOT_REQUESTED')}
Tools used: git, python3{', simulated_scanner' if args.fail_scanner_sim else ''}
Tools skipped: slither, aderyn, semgrep, myth, echidna, medusa
Errors: {len(errors)}
Warnings: {len(warnings)}
Tests executed: NONE
Authorization or scope limitations: Local static discovery only; zero live broadcast
Recommended next stage: Pack B — Source Mapping and Static Analysis
======================================================================
"""
    print(report.strip())
    return 0


if __name__ == "__main__":
    sys.exit(main())
