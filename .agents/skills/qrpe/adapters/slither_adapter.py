#!/usr/bin/env python3
"""
Slither Deterministic Adapter for QRPE and Oracle Agentic Mesh (OAM).
Verifies tool availability, enforces dry-run precedence, executes scanner within timeout limits,
captures SARIF output, atomically writes receipt.json, and strictly propagates scanner failure exit codes.
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

sys.path.insert(0, os.path.dirname(__file__))
from utils import find_tool


def get_tool_version(tool_path: str) -> str | None:
    """Extract tool version from tool --version."""
    try:
        res = subprocess.run([tool_path, "--version"], capture_output=True, text=True, timeout=5)
        if res.returncode == 0:
            line = res.stdout.strip().splitlines()[0] if res.stdout.strip() else ""
            if " " in line:
                return line.split(" ")[-1]
            return line if line else None
    except Exception:
        pass
    return None


def atomic_write_json(file_path: str, data: dict) -> None:
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


def check_help_flags(tool_path: str, flags: list[str]) -> bool:
    """Check required flags exist in tool --help."""
    try:
        res = subprocess.run([tool_path, "--help"], capture_output=True, text=True, timeout=10)
        help_text = res.stdout + res.stderr
        for flag in flags:
            flag_clean = flag.split("=")[0]
            if flag_clean not in help_text:
                print(f"[FAIL] Flag '{flag_clean}' not found in '{tool_path} --help'", file=sys.stderr)
                return False
        return True
    except Exception as e:
        print(f"[FAIL] Help check encountered error: {e}", file=sys.stderr)
        return False


def main():
    parser = argparse.ArgumentParser(description="QRPE / OAM Slither Adapter")
    parser.add_argument("--target", required=True, help="Target build directory")
    parser.add_argument("--output-dir", required=True, help="Scan output directory")
    parser.add_argument("--exclude-paths", default="", help="Pipe-separated paths to exclude")
    parser.add_argument("--dry-run", action="store_true", default=False, help="Preview without execution")
    parser.add_argument("--confirm", action="store_true", default=False, help="Authorize live execution")
    parser.add_argument("--timeout", type=int, default=300, help="Execution timeout in seconds")
    # Adversarial test simulation hooks
    parser.add_argument("--scanner-fail-sim", action="store_true", default=False, help="Simulate scanner failure")
    parser.add_argument("--fail-receipt-sim", action="store_true", default=False, help="Simulate receipt write failure")
    parser.add_argument("--timeout-sim", action="store_true", default=False, help="Simulate scanner execution timeout")
    args = parser.parse_args()

    is_dry_run = args.dry_run or not args.confirm

    tool_path = find_tool("slither")
    if not tool_path:
        if is_dry_run:
            tool_path = "slither"
        else:
            print("[FAIL] 'slither' executable not found on PATH or standard directories", file=sys.stderr)
            sys.exit(1)

    sarif_file = os.path.join(args.output_dir, "slither.sarif")
    cmd_for_receipt = [tool_path, args.target, "--sarif", sarif_file, "--fail-none"]
    if args.exclude_paths:
        cmd_for_receipt.extend(["--filter-paths", args.exclude_paths])

    # Invariant: --dry-run strictly takes precedence over --confirm
    if is_dry_run:
        print(f"[DRY-RUN] Verified slither command: {' '.join(cmd_for_receipt)}")
        sys.exit(0)

    flags_to_check = ["--sarif", "--fail-none"]
    if args.exclude_paths:
        flags_to_check.append("--filter-paths")

    if not check_help_flags(tool_path, flags_to_check):
        sys.exit(1)

    # Live execution authorized
    os.makedirs(args.output_dir, exist_ok=True)
    tool_version = get_tool_version(tool_path)
    t0 = time.time()

    # Stage scanner output to temporary file so existing valid artifacts survive failures intact
    tmp_out_file = os.path.join(args.output_dir, f".tmp.slither.{os.getpid()}.sarif")
    actual_cmd = [tool_path, args.target, "--sarif", tmp_out_file, "--fail-none"]
    if args.exclude_paths:
        actual_cmd.extend(["--filter-paths", args.exclude_paths])

    # Ensure forge, solc, and toolchain bins are available on PATH for crytic_compile
    env = os.environ.copy()
    home = os.path.expanduser("~")
    extra_paths = [
        os.path.join(home, ".foundry", "bin"),
        os.path.join(home, ".local", "bin"),
        os.path.join(home, ".cargo", "bin"),
    ]
    env["PATH"] = ":".join(extra_paths) + ":" + env.get("PATH", "")

    if args.timeout_sim:
        print(f"[FAIL] Scanner execution timed out after {args.timeout}s", file=sys.stderr)
        receipt = {
            "tool": "slither",
            "version": tool_version,
            "command": cmd_for_receipt,
            "target": args.target,
            "exit_code": 124,
            "duration_seconds": float(args.timeout),
            "output_file": sarif_file,
            "sha256": "",
            "error": "EXECUTION_TIMEOUT: Process execution timed out",
        }
        try:
            atomic_write_json(os.path.join(args.output_dir, "receipt.json"), receipt)
        except Exception:
            pass
        sys.exit(124)

    if args.scanner_fail_sim:
        res_returncode = 1
        res_stdout = ""
        res_stderr = "Simulated Slither scanner error: fatal syntax or compilation error"
        duration = 0.05
    else:
        try:
            res = subprocess.run(actual_cmd, env=env, capture_output=True, text=True, timeout=args.timeout)
            res_returncode = res.returncode
            res_stdout = res.stdout
            res_stderr = res.stderr
            duration = time.time() - t0
        except subprocess.TimeoutExpired as te:
            duration = time.time() - t0
            print(f"[FAIL] Scanner execution timed out after {args.timeout}s", file=sys.stderr)
            if os.path.exists(tmp_out_file):
                try:
                    os.remove(tmp_out_file)
                except OSError:
                    pass
            receipt = {
                "tool": "slither",
                "version": tool_version,
                "command": cmd_for_receipt,
                "target": args.target,
                "exit_code": 124,
                "duration_seconds": duration,
                "output_file": sarif_file,
                "sha256": "",
                "error": f"EXECUTION_TIMEOUT: {te}",
            }
            try:
                atomic_write_json(os.path.join(args.output_dir, "receipt.json"), receipt)
            except Exception:
                pass
            sys.exit(124)
        except Exception as e:
            duration = time.time() - t0
            print(f"[FAIL] Scanner execution failed: {e}", file=sys.stderr)
            if os.path.exists(tmp_out_file):
                try:
                    os.remove(tmp_out_file)
                except OSError:
                    pass
            receipt = {
                "tool": "slither",
                "version": tool_version,
                "command": cmd_for_receipt,
                "target": args.target,
                "exit_code": 1,
                "duration_seconds": duration,
                "output_file": sarif_file,
                "sha256": "",
                "error": f"EXECUTION_FAILED: {e}",
            }
            try:
                atomic_write_json(os.path.join(args.output_dir, "receipt.json"), receipt)
            except Exception:
                pass
            sys.exit(1)

    sha256 = ""
    if res_returncode == 0 and os.path.exists(tmp_out_file):
        try:
            os.replace(tmp_out_file, sarif_file)
            with open(sarif_file, "rb") as f:
                sha256 = hashlib.sha256(f.read()).hexdigest()
        except Exception as e:
            print(f"[FAIL] Failed to promote staged output: {e}", file=sys.stderr)
            res_returncode = 1
    else:
        if os.path.exists(tmp_out_file):
            try:
                os.remove(tmp_out_file)
            except OSError:
                pass

    receipt = {
        "tool": "slither",
        "version": tool_version,
        "command": cmd_for_receipt,
        "target": args.target,
        "exit_code": res_returncode,
        "duration_seconds": duration,
        "output_file": sarif_file,
        "sha256": sha256,
        "stdout_snippet": res_stdout[:500] if res_stdout else "",
        "stderr_snippet": res_stderr[:500] if res_stderr else "",
    }

    if args.fail_receipt_sim:
        print("[FAIL] Simulated receipt serialization failure: permission denied", file=sys.stderr)
        sys.exit(1)

    receipt_path = os.path.join(args.output_dir, "receipt.json")
    try:
        atomic_write_json(receipt_path, receipt)
    except Exception as e:
        print(f"[FAIL] Failed to write receipt: {e}", file=sys.stderr)
        sys.exit(1)

    if res_returncode != 0:
        print(f"[FAIL] Slither exited with code {res_returncode}: {res_stderr.strip()}", file=sys.stderr)
        sys.exit(res_returncode)

    print(f"[OK] Slither executed in {duration:.2f}s, SHA-256: {sha256[:16]}...")
    sys.exit(0)


if __name__ == "__main__":
    main()
