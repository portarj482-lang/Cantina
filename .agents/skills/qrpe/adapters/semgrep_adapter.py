#!/usr/bin/env python3
"""
Semgrep Deterministic Adapter for QRPE and Oracle Agentic Mesh (OAM).
Verifies tool availability, enforces dry-run precedence, executes scanner within timeout limits,
captures JSON output, atomically writes receipt.json, and strictly propagates scanner failure exit codes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
from utils import find_tool


def get_scanner_env() -> dict[str, str]:
    """Ensure PATH includes user-local bin directories for semgrep & pysemgrep."""
    env = os.environ.copy()
    home = os.path.expanduser("~")
    extra_paths = [
        os.path.join(home, ".local", "bin"),
        os.path.join(home, ".cargo", "bin"),
        os.path.join(home, ".foundry", "bin"),
    ]
    current_path = env.get("PATH", "")
    for p in extra_paths:
        if p not in current_path:
            current_path = f"{p}:{current_path}"
    env["PATH"] = current_path
    return env


def get_tool_version(tool_path: str, env: dict[str, str]) -> str | None:
    """Retrieve semgrep version string."""
    try:
        res = subprocess.run([tool_path, "--version"], capture_output=True, text=True, timeout=10, env=env)
        if res.returncode == 0:
            lines = res.stdout.strip().splitlines()
            if lines:
                return lines[0].strip().split()[-1]
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


def main():
    parser = argparse.ArgumentParser(description="QRPE / OAM Semgrep Adapter")
    parser.add_argument("--target", required=True, help="Target root directory")
    parser.add_argument("--output-dir", required=True, help="Scan output directory")
    parser.add_argument("--config", default="auto", help="Rule config (default: auto)")
    parser.add_argument("--dry-run", action="store_true", default=False, help="Preview without execution")
    parser.add_argument("--confirm", action="store_true", default=False, help="Authorize live execution")
    parser.add_argument("--timeout", type=int, default=300, help="Execution timeout in seconds")
    # Adversarial test simulation hooks
    parser.add_argument("--scanner-fail-sim", action="store_true", default=False, help="Simulate scanner failure")
    parser.add_argument("--fail-receipt-sim", action="store_true", default=False, help="Simulate receipt write failure")
    parser.add_argument("--timeout-sim", action="store_true", default=False, help="Simulate scanner execution timeout")
    args = parser.parse_args()

    is_dry_run = args.dry_run or not args.confirm

    tool_path = find_tool("semgrep")
    if not tool_path:
        if is_dry_run:
            tool_path = "semgrep"
        else:
            print("[FAIL] 'semgrep' executable not found on PATH or standard directories", file=sys.stderr)
            sys.exit(1)

    env = get_scanner_env()
    out_file = os.path.join(args.output_dir, "semgrep.json")
    cmd_for_receipt = [tool_path, "scan", "--config", args.config, "--json", "-o", out_file, args.target]

    # Invariant: --dry-run strictly takes precedence over --confirm
    if is_dry_run:
        print(f"[DRY-RUN] Verified semgrep command: {' '.join(cmd_for_receipt)}")
        sys.exit(0)

    # Verify flags in help
    try:
        res = subprocess.run([tool_path, "scan", "--help"], capture_output=True, text=True, timeout=10, env=env)
        if "--config" not in res.stdout and "-c" not in res.stdout:
            print("[FAIL] Semgrep help check failed for required flags", file=sys.stderr)
            sys.exit(1)
    except Exception as e:
        print(f"[FAIL] Semgrep help check encountered error: {e}", file=sys.stderr)
        sys.exit(1)

    # Live execution authorized
    os.makedirs(args.output_dir, exist_ok=True)
    tool_version = get_tool_version(tool_path, env)
    t0 = time.time()

    # Stage scanner output to temporary file so existing valid artifacts survive failures intact
    tmp_out_file = os.path.join(args.output_dir, f".tmp.semgrep.{os.getpid()}.json")
    actual_cmd = [
        tool_path, "scan",
        "--config", args.config,
        "--exclude", "scans",
        "--exclude", ".git",
        "--json",
        "-o", tmp_out_file,
        args.target,
    ]

    if args.timeout_sim:
        print(f"[FAIL] Scanner execution timed out after {args.timeout}s (process tree terminated)", file=sys.stderr)
        receipt = {
            "tool": "semgrep",
            "version": tool_version,
            "command": cmd_for_receipt,
            "target": args.target,
            "config": args.config,
            "exit_code": 124,
            "duration_seconds": float(args.timeout),
            "output_file": out_file,
            "sha256": "",
            "error": "EXECUTION_TIMEOUT: Process execution timed out",
            "process_tree_terminated": True,
        }
        try:
            atomic_write_json(os.path.join(args.output_dir, "receipt.json"), receipt)
        except Exception:
            pass
        sys.exit(124)

    if args.scanner_fail_sim:
        res_returncode = 1
        res_stdout = ""
        res_stderr = "Simulated Semgrep scanner error: syntax error encountered"
        duration = 0.05
    else:
        try:
            # Launch in new process group to enable reliable process tree termination
            proc = subprocess.Popen(
                actual_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                start_new_session=True,
                env=env,
            )
            try:
                res_stdout, res_stderr = proc.communicate(timeout=args.timeout)
                res_returncode = proc.returncode
            except subprocess.TimeoutExpired as te:
                # Terminate entire process tree
                try:
                    pgid = os.getpgid(proc.pid)
                    os.killpg(pgid, signal.SIGTERM)
                    time.sleep(0.5)
                    os.killpg(pgid, signal.SIGKILL)
                except OSError:
                    pass
                try:
                    proc.kill()
                except OSError:
                    pass
                res_stdout, res_stderr = proc.communicate()
                raise te
            duration = time.time() - t0
        except subprocess.TimeoutExpired as te:
            duration = time.time() - t0
            print(f"[FAIL] Scanner execution timed out after {args.timeout}s (process tree terminated)", file=sys.stderr)
            if os.path.exists(tmp_out_file):
                try:
                    os.remove(tmp_out_file)
                except OSError:
                    pass
            receipt = {
                "tool": "semgrep",
                "version": tool_version,
                "command": cmd_for_receipt,
                "target": args.target,
                "config": args.config,
                "exit_code": 124,
                "duration_seconds": duration,
                "output_file": out_file,
                "sha256": "",
                "error": f"EXECUTION_TIMEOUT: {te}",
                "process_tree_terminated": True,
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
                "tool": "semgrep",
                "version": tool_version,
                "command": cmd_for_receipt,
                "target": args.target,
                "config": args.config,
                "exit_code": 1,
                "duration_seconds": duration,
                "output_file": out_file,
                "sha256": "",
                "error": f"EXECUTION_FAILED: {e}",
                "process_tree_terminated": True,
            }
            try:
                atomic_write_json(os.path.join(args.output_dir, "receipt.json"), receipt)
            except Exception:
                pass
            sys.exit(1)

    sha256 = ""
    if res_returncode == 0 and os.path.exists(tmp_out_file):
        # Swap staged output to destination atomically
        try:
            os.replace(tmp_out_file, out_file)
            with open(out_file, "rb") as f:
                sha256 = hashlib.sha256(f.read()).hexdigest()
            # Also maintain canonical raw/semgrep-output.json
            out_alias = os.path.join(args.output_dir, "semgrep-output.json")
            shutil.copy2(out_file, out_alias)
        except Exception as e:
            print(f"[FAIL] Failed to promote staged output: {e}", file=sys.stderr)
            res_returncode = 1
    else:
        # Failure: clean up temporary file; existing artifacts stay untouched
        if os.path.exists(tmp_out_file):
            try:
                os.remove(tmp_out_file)
            except OSError:
                pass

    receipt = {
        "tool": "semgrep",
        "version": tool_version,
        "command": cmd_for_receipt,
        "target": args.target,
        "config": args.config,
        "exit_code": res_returncode,
        "duration_seconds": duration,
        "output_file": out_file,
        "sha256": sha256,
        "stdout_snippet": res_stdout[:500] if res_stdout else "",
        "stderr_snippet": res_stderr[:500] if res_stderr else "",
    }

    # Simulate receipt failure if requested
    if args.fail_receipt_sim:
        print("[FAIL] Simulated receipt serialization failure: permission denied", file=sys.stderr)
        sys.exit(1)

    receipt_path = os.path.join(args.output_dir, "receipt.json")
    try:
        atomic_write_json(receipt_path, receipt)
    except Exception as e:
        print(f"[FAIL] Failed to write receipt: {e}", file=sys.stderr)
        sys.exit(1)

    # Invariant: Propagate scanner failure exit code
    if res_returncode != 0:
        print(f"[FAIL] Semgrep exited with code {res_returncode}: {res_stderr.strip()}", file=sys.stderr)
        sys.exit(res_returncode)

    print(f"[OK] Semgrep executed in {duration:.2f}s, SHA-256: {sha256[:16]}...")
    sys.exit(0)


if __name__ == "__main__":
    main()
