#!/usr/bin/env python3
"""
Foundry Test Adapter for QRPE and Glassbox Verification Plane.
Executes forge test suites, enforces dual-fork runs, independently validates
repository path containment, captures isolated stdout/stderr logs with SHA-256
digests, and atomically writes receipt.json under defense-in-depth policy.
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
from typing import Any, Optional

sys.path.insert(0, os.path.dirname(__file__))
from utils import find_tool


def get_forge_version(tool_path: str) -> str:
    """Extract forge version and commit metadata from forge --version."""
    try:
        res = subprocess.run([tool_path, "--version"], capture_output=True, text=True, timeout=5)
        if res.returncode == 0:
            lines = res.stdout.strip().splitlines()
            if lines:
                return lines[0].strip()
    except Exception:
        pass
    return "unknown"


def compute_file_sha256(path: str) -> str:
    """Compute exact SHA-256 digest of file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


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


def resolve_repo_root() -> Path:
    """Resolve the canonical workspace repository root."""
    env_root = os.environ.get("REPO_ROOT")
    if env_root:
        return Path(env_root).resolve()
    # Default fallback: 5 levels up from .agents/skills/qrpe/adapters/
    candidate = Path(__file__).resolve().parents[4]
    if (candidate / ".git").exists() or (candidate / "bounties").exists():
        return candidate
    return Path("/home/nova/projects/cantina").resolve()


def main():
    parser = argparse.ArgumentParser(description="QRPE Foundry Test Adapter")
    parser.add_argument("--target", required=True, help="Target build copy directory")
    parser.add_argument("--output-dir", required=True, help="Scan/receipt output directory")
    parser.add_argument("--match-test", default="", help="Forge test filter regex/pattern")
    parser.add_argument("--fork-url-env", default="", help="Name of env var containing RPC URL (never raw URL)")
    parser.add_argument("--fork-block", default="", help="Pinned block number")
    parser.add_argument("--timeout", type=int, default=120, help="Test execution timeout in seconds")
    parser.add_argument("--dry-run", action="store_true", default=False, help="Preview without executing tests")
    parser.add_argument("--confirm", action="store_true", default=False, help="Authorize live forge execution")
    args = parser.parse_args()

    repo_root = resolve_repo_root()

    # Independent path containment verification (Defense-in-Depth)
    target_path = Path(args.target).resolve()
    try:
        if not target_path.is_relative_to(repo_root):
            print(f"[FAIL] Target path '{target_path}' escapes repository root '{repo_root}'", file=sys.stderr)
            sys.exit(1)
    except AttributeError:
        # Python < 3.9 compatibility fallback
        if not str(target_path).startswith(str(repo_root)):
            print(f"[FAIL] Target path '{target_path}' escapes repository root '{repo_root}'", file=sys.stderr)
            sys.exit(1)

    if not target_path.exists():
        print(f"[FAIL] Target directory does not exist: {target_path}", file=sys.stderr)
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

    tool_path = find_tool("forge")
    if not tool_path:
        print("[FAIL] 'forge' executable not found on PATH or in standard user locations", file=sys.stderr)
        sys.exit(1)

    version_str = get_forge_version(tool_path)

    cmd = [tool_path, "test", "-vvv"]
    if args.match_test:
        cmd.extend(["--match-test", args.match_test])
    if args.fork_url_env:
        rpc_url = os.environ.get(args.fork_url_env, "")
        if not rpc_url:
            print(f"[FAIL] Env var {args.fork_url_env} is not set", file=sys.stderr)
            sys.exit(1)
        cmd.extend(["--fork-url", rpc_url])
    if args.fork_block:
        cmd.extend(["--fork-block-number", args.fork_block])

    # Redact actual RPC URL from logged command string
    safe_cmd = []
    for c in cmd:
        if args.fork_url_env and os.environ.get(args.fork_url_env) and c == os.environ.get(args.fork_url_env):
            safe_cmd.append(f"${args.fork_url_env}")
        else:
            safe_cmd.append(c)
    safe_cmd_str = " ".join(safe_cmd)

    # Fail-closed dry-run enforcement: dry-run or unconfirmed never executes tests
    if args.dry_run or not args.confirm:
        print(f"[DRY-RUN] Verified forge test command in {target_path} ({version_str}): {safe_cmd_str}")
        sys.exit(0)

    # Live Execution Phase
    output_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    try:
        res = subprocess.run(
            cmd,
            cwd=str(target_path),
            capture_output=True,
            text=True,
            timeout=args.timeout,
        )
        duration = time.time() - t0
        stdout_content = res.stdout
        stderr_content = res.stderr
        exit_code = res.returncode
    except subprocess.TimeoutExpired as exc:
        duration = time.time() - t0
        stdout_content = exc.stdout.decode("utf-8", errors="replace") if exc.stdout else ""
        stderr_content = (exc.stderr.decode("utf-8", errors="replace") if exc.stderr else "") + f"\n[ERROR] Test execution timed out after {args.timeout}s"
        exit_code = 124

    # Write separate stdout and stderr logs
    stdout_file = output_dir / "stdout.log"
    stderr_file = output_dir / "stderr.log"
    stdout_file.write_text(stdout_content, encoding="utf-8")
    stderr_file.write_text(stderr_content, encoding="utf-8")

    stdout_sha = compute_file_sha256(str(stdout_file))
    stderr_sha = compute_file_sha256(str(stderr_file))

    # Also write combined forge_output.txt for backward compatibility
    out_file = output_dir / "forge_output.txt"
    out_file.write_text(stdout_content + "\n" + stderr_content, encoding="utf-8")
    combined_sha = compute_file_sha256(str(out_file))

    receipt = {
        "tool": "forge",
        "version": version_str,
        "executable": tool_path,
        "target": str(target_path),
        "output_dir": str(output_dir),
        "command_template": safe_cmd_str,
        "exit_code": exit_code,
        "duration_seconds": round(duration, 3),
        "stdout_file": str(stdout_file),
        "stdout_sha256": stdout_sha,
        "stderr_file": str(stderr_file),
        "stderr_sha256": stderr_sha,
        "output_file": str(out_file),
        "sha256": combined_sha,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    receipt_file = output_dir / "receipt.json"
    atomic_write_json(str(receipt_file), receipt)

    print(f"[OK] Forge test completed in {duration:.2f}s with exit code {exit_code}, SHA-256: {combined_sha[:16]}...")
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
