#!/usr/bin/env python3
"""
Medusa Deterministic Adapter for QRPE and Glassbox Verification Plane.
Verifies tool availability, checks CLI option compatibility against medusa fuzz --help,
enforces dry-run precedence, executes fuzzer within bounded timeout limits,
captures raw stdout/stderr logs, atomically writes receipt.json, and strictly
propagates fuzzer execution status.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(__file__))
try:
    from utils import find_tool
except ImportError:
    def find_tool(name: str) -> Optional[str]:
        return shutil.which(name)


def resolve_medusa_binary() -> Optional[str]:
    """Find medusa on PATH or standard install locations."""
    tool = find_tool("medusa")
    if tool and os.path.isfile(tool) and os.access(tool, os.X_OK):
        return tool

    common_paths = [
        os.path.expanduser("~/.local/bin/medusa"),
        "/usr/local/bin/medusa",
        "/usr/bin/medusa",
    ]
    for p in common_paths:
        if os.path.isfile(p) and os.access(p, os.X_OK):
            return p
    return None


def get_tool_version(tool_path: str) -> Optional[str]:
    """Extract tool version from medusa --version."""
    try:
        res = subprocess.run([tool_path, "--version"], capture_output=True, text=True, timeout=5)
        if res.returncode == 0:
            lines = res.stdout.strip().splitlines()
            if lines:
                return lines[0].strip()
    except Exception:
        pass
    return None


def check_help_flags(tool_path: str, flags: list[str]) -> tuple[bool, list[str]]:
    """Check required flags exist in medusa fuzz --help. Returns (all_supported, missing_flags)."""
    try:
        res = subprocess.run([tool_path, "fuzz", "--help"], capture_output=True, text=True, timeout=10)
        help_text = res.stdout + res.stderr
        missing = []
        for flag in flags:
            clean_flag = flag.split("=")[0]
            if clean_flag not in help_text:
                missing.append(clean_flag)
        return (len(missing) == 0, missing)
    except Exception as e:
        print(f"[FAIL] Help check encountered error: {e}", file=sys.stderr)
        return (False, flags)


def atomic_write_json(file_path: str, data: dict[str, Any]) -> None:
    """Atomically write JSON data to file_path using temporary file replacement."""
    dir_name = os.path.dirname(file_path)
    if dir_name:
        os.makedirs(dir_name, exist_ok=True)
    tmp_path = f"{file_path}.tmp.{os.getpid()}"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, file_path)
    except Exception:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
        raise


def atomic_write_text(file_path: str, content: str) -> None:
    """Atomically write text data to file_path using temporary file replacement and fsync."""
    dir_name = os.path.dirname(file_path)
    if dir_name:
        os.makedirs(dir_name, exist_ok=True)
    tmp_path = f"{file_path}.tmp.{os.getpid()}"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, file_path)
    except Exception:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
        raise


def resolve_repo_root() -> Path:
    """Resolve the canonical workspace repository root."""
    env_root = os.environ.get("REPO_ROOT")
    if env_root:
        return Path(env_root).resolve()
    candidate = Path(__file__).resolve().parents[4]
    return candidate


def compute_file_sha256(path: str) -> str:
    """Compute exact SHA-256 digest of file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser(description="QRPE / Glassbox Medusa Dynamic Property Fuzzing Adapter")
    parser.add_argument("--target", required=True, help="Target Solidity source or build directory")
    parser.add_argument("--output-dir", required=True, help="Artifact / scan output directory")
    parser.add_argument("--config", default="", help="Path to Medusa JSON config file")
    parser.add_argument("--timeout", type=int, default=60, help="Campaign execution timeout in seconds")
    parser.add_argument("--test-limit", type=int, default=None, help="Maximum number of test sequences/transactions")
    parser.add_argument("--workers", type=int, default=None, help="Number of worker threads")
    parser.add_argument("--seed", type=int, default=None, help="Deterministic fuzzing seed")
    parser.add_argument("--dry-run", action="store_true", default=False, help="Preview without fuzzing execution")
    parser.add_argument("--confirm", action="store_true", default=False, help="Explicitly authorize live fuzzing execution")
    args = parser.parse_args()

    repo_root = resolve_repo_root()

    # Independent path containment verification (Defense-in-Depth per AGENTS.md Rule 8)
    target_path = Path(args.target).resolve()
    try:
        if not target_path.is_relative_to(repo_root):
            print(f"[FAIL] Target path '{target_path}' escapes repository root '{repo_root}'", file=sys.stderr)
            sys.exit(1)
    except AttributeError:
        if not str(target_path).startswith(str(repo_root)):
            print(f"[FAIL] Target path '{target_path}' escapes repository root '{repo_root}'", file=sys.stderr)
            sys.exit(1)

    raw_target = Path(args.target)
    if raw_target.is_symlink():
        leaf_dest = raw_target.resolve()
        try:
            if not leaf_dest.is_relative_to(repo_root):
                print(f"[FAIL] Target leaf symlink '{raw_target}' escapes repository root: {leaf_dest}", file=sys.stderr)
                sys.exit(1)
        except AttributeError:
            if not str(leaf_dest).startswith(str(repo_root)):
                print(f"[FAIL] Target leaf symlink '{raw_target}' escapes repository root: {leaf_dest}", file=sys.stderr)
                sys.exit(1)

    output_dir = Path(args.output_dir).resolve()
    try:
        if not output_dir.is_relative_to(repo_root):
            print(f"[FAIL] Output directory '{output_dir}' escapes repository root '{repo_root}'", file=sys.stderr)
            sys.exit(1)
    except AttributeError:
        if not str(output_dir).startswith(str(repo_root)):
            print(f"[FAIL] Output directory '{output_dir}' escapes repository root '{repo_root}'", file=sys.stderr)
            sys.exit(1)

    raw_output = Path(args.output_dir)
    if raw_output.is_symlink():
        leaf_out = raw_output.resolve()
        try:
            if not leaf_out.is_relative_to(repo_root):
                print(f"[FAIL] Output leaf symlink '{raw_output}' escapes repository root: {leaf_out}", file=sys.stderr)
                sys.exit(1)
        except AttributeError:
            if not str(leaf_out).startswith(str(repo_root)):
                print(f"[FAIL] Output leaf symlink '{raw_output}' escapes repository root: {leaf_out}", file=sys.stderr)
                sys.exit(1)

    # Validate target exists
    if not target_path.exists():
        print(f"[FAIL] Target does not exist: {args.target}", file=sys.stderr)
        sys.exit(1)

    is_dry_run = args.dry_run or not args.confirm

    tool_path = resolve_medusa_binary()
    if not tool_path:
        if is_dry_run:
            tool_path = "medusa"
        else:
            print("[FAIL] 'medusa' executable not found on PATH or in standard user locations", file=sys.stderr)
            sys.exit(1)

    version_str = get_tool_version(tool_path) if tool_path != "medusa" else "medusa (dry-run simulation)"

    # Validate requested flags against tool --help
    flags_to_check = ["--no-color", "--timeout"]
    if args.config:
        flags_to_check.append("--config")
    if args.test_limit is not None:
        flags_to_check.append("--test-limit")
    if args.workers is not None:
        flags_to_check.append("--workers")

    supported, missing = check_help_flags(tool_path, flags_to_check)
    if not supported:
        print(f"[FAIL] Installed Medusa does not support required flags: {missing}", file=sys.stderr)
        sys.exit(1)

    # Build argument array
    cmd: list[str] = [tool_path, "fuzz", "--no-color"]
    if args.config:
        cmd.extend(["--config", str(Path(args.config).resolve())])
    if target_path.is_file():
        cmd.extend(["--compilation-target", str(target_path)])
    elif target_path.is_dir() and not args.config:
        cmd.extend(["--compilation-target", str(target_path)])

    if args.timeout:
        cmd.extend(["--timeout", str(args.timeout)])
    if args.test_limit is not None:
        cmd.extend(["--test-limit", str(args.test_limit)])
    if args.workers is not None:
        cmd.extend(["--workers", str(args.workers)])

    safe_cmd_str = " ".join(cmd)

    # Fail-closed dry-run check: dry-run or unconfirmed never executes
    if args.dry_run or not args.confirm:
        print(f"[DRY-RUN] Verified medusa command for {target_path} ({version_str}):")
        print(f"          {safe_cmd_str}")
        print("[PREFLIGHT_PASSED] Preflight completed; fuzzing campaign was not executed.")
        sys.exit(0)

    # Live Execution
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    stdout_path = output_dir / "stdout.log"
    stderr_path = output_dir / "stderr.log"

    t0 = time.time()
    proc = None
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(target_path if target_path.is_dir() else target_path.parent),
            capture_output=True,
            text=True,
            timeout=args.timeout + 15,  # Supervisor grace margin
        )
        duration = time.time() - t0
        stdout_content = proc.stdout
        stderr_content = proc.stderr
        exit_code = proc.returncode
    except subprocess.TimeoutExpired as exc:
        duration = time.time() - t0
        stdout_content = exc.stdout.decode("utf-8", errors="replace") if exc.stdout else ""
        stderr_content = (exc.stderr.decode("utf-8", errors="replace") if exc.stderr else "") + "\n[ERROR] Campaign timed out."
        exit_code = 124

    # Write logs atomically with fsync
    atomic_write_text(str(stdout_path), stdout_content)
    atomic_write_text(str(stderr_path), stderr_content)

    stdout_sha = compute_file_sha256(str(stdout_path))
    stderr_sha = compute_file_sha256(str(stderr_path))

    receipt = {
        "tool": "medusa",
        "version": version_str,
        "executable": tool_path,
        "target": str(target_path),
        "command": safe_cmd_str,
        "exit_code": exit_code,
        "duration_seconds": round(duration, 3),
        "stdout_file": str(stdout_path),
        "stdout_sha256": stdout_sha,
        "stderr_file": str(stderr_path),
        "stderr_sha256": stderr_sha,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    receipt_file = output_dir / "receipt.json"
    atomic_write_json(str(receipt_file), receipt)

    print(f"[OK] Medusa process finished in {duration:.2f}s with status {exit_code}")
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
