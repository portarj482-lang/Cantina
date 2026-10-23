#!/usr/bin/env python3
"""
Echidna Deterministic Adapter for QRPE and Glassbox Verification Plane.
Verifies tool availability, checks CLI option compatibility against echidna --help,
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
from typing import Any, List, Optional

sys.path.insert(0, os.path.dirname(__file__))
from utils import find_tool


def resolve_echidna_binary() -> Optional[str]:
    """Find echidna on PATH or standard install locations."""
    tool = find_tool("echidna")
    if tool and os.path.isfile(tool) and os.access(tool, os.X_OK):
        return tool

    common_paths = [
        os.path.expanduser("~/.local/bin/echidna"),
        "/usr/local/bin/echidna",
        "/usr/bin/echidna",
    ]
    for p in common_paths:
        if os.path.isfile(p) and os.access(p, os.X_OK):
            return p
    return None


def get_tool_version(tool_path: str) -> Optional[str]:
    """Extract tool version from echidna --version."""
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
    """Check required flags exist in tool --help. Returns (all_supported, missing_flags)."""
    try:
        res = subprocess.run([tool_path, "--help"], capture_output=True, text=True, timeout=10)
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


def compute_file_sha256(path: str) -> str:
    """Compute exact SHA-256 digest of file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser(description="QRPE / Glassbox Echidna Dynamic Fuzzing Adapter")
    parser.add_argument("--target", required=True, help="Target Solidity source or build directory")
    parser.add_argument("--output-dir", required=True, help="Artifact / scan output directory")
    parser.add_argument("--config", default="", help="Path to Echidna YAML/JSON config file")
    parser.add_argument("--contract", default="", help="Target contract to fuzz")
    parser.add_argument("--test-mode", default="property", help="Echidna test mode (property, assertion, overflow, exploration)")
    parser.add_argument("--test-limit", type=int, default=None, help="Maximum number of test sequences")
    parser.add_argument("--seed", type=int, default=None, help="Deterministic fuzzing seed")
    parser.add_argument("--timeout", type=int, default=60, help="Campaign execution timeout in seconds")
    parser.add_argument("--format", default="json", choices=["json", "text", "none"], help="Output format")
    parser.add_argument("--dry-run", action="store_true", default=False, help="Preview without fuzzing execution")
    parser.add_argument("--confirm", action="store_true", default=False, help="Explicitly authorize live fuzzing execution")
    args = parser.parse_args()

    is_dry_run = args.dry_run or not args.confirm

    tool_path = resolve_echidna_binary()
    if not tool_path:
        if is_dry_run:
            tool_path = "echidna"
        else:
            print("[FAIL] 'echidna' executable not found on PATH or in standard user locations", file=sys.stderr)
            sys.exit(1)

    version_str = get_tool_version(tool_path) if tool_path != "echidna" else "Echidna (dry-run simulation)"

    # Validate target exists
    target_path = Path(args.target).resolve()
    if not target_path.exists():
        print(f"[FAIL] Target does not exist: {args.target}", file=sys.stderr)
        sys.exit(1)

    # Validate requested flags against tool --help
    flags_to_check = ["--format", "--timeout"]
    if args.config:
        flags_to_check.append("--config")
    if args.contract:
        flags_to_check.append("--contract")
    if args.test_mode:
        flags_to_check.append("--test-mode")
    if args.test_limit is not None:
        flags_to_check.append("--test-limit")
    if args.seed is not None:
        flags_to_check.append("--seed")

    supported, missing = check_help_flags(tool_path, flags_to_check)
    if not supported:
        print(f"[FAIL] Installed Echidna does not support required flags: {missing}", file=sys.stderr)
        sys.exit(1)

    # Build argument array
    cmd: list[str] = [tool_path, str(target_path)]
    if args.format:
        cmd.extend(["--format", args.format])
    if args.config:
        cmd.extend(["--config", str(Path(args.config).resolve())])
    if args.contract:
        cmd.extend(["--contract", args.contract])
    if args.test_mode:
        cmd.extend(["--test-mode", args.test_mode])
    if args.test_limit is not None:
        cmd.extend(["--test-limit", str(args.test_limit)])
    if args.seed is not None:
        cmd.extend(["--seed", str(args.seed)])
    if args.timeout:
        cmd.extend(["--timeout", str(args.timeout)])

    safe_cmd_str = " ".join(cmd)

    # Fail-closed dry-run check: dry-run or unconfirmed never executes
    if args.dry_run or not args.confirm:
        print(f"[DRY-RUN] Verified echidna command for {target_path} ({version_str}):")
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
            timeout=args.timeout + 15,  # Add grace margin to process supervisor
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

    # Write logs
    stdout_path.write_text(stdout_content, encoding="utf-8")
    stderr_path.write_text(stderr_content, encoding="utf-8")

    stdout_sha = compute_file_sha256(str(stdout_path))
    stderr_sha = compute_file_sha256(str(stderr_path))

    receipt = {
        "tool": "echidna",
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

    print(f"[OK] Echidna process finished in {duration:.2f}s with status {exit_code}")
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
