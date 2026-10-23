#!/usr/bin/env python3
"""
Slither Deterministic Adapter for QRPE.
Verifies help flags, captures SARIF, and computes SHA-256 evidence digests.
"""
import sys
import os
import shutil
import hashlib
import time
import subprocess
import argparse
import json

sys.path.insert(0, os.path.dirname(__file__))
from utils import find_tool

def check_help_flags(tool_path: str, flags: list[str]) -> bool:
    res = subprocess.run([tool_path, "--help"], capture_output=True, text=True)
    help_text = res.stdout + res.stderr
    for flag in flags:
        flag_clean = flag.split("=")[0]
        if flag_clean not in help_text:
            print(f"[FAIL] Flag '{flag_clean}' not found in '{tool_path} --help'")
            return False
    return True

def main():
    parser = argparse.ArgumentParser(description="QRPE Slither Adapter")
    parser.add_argument("--target", required=True, help="Target build directory")
    parser.add_argument("--output-dir", required=True, help="Scan output directory")
    parser.add_argument("--exclude-paths", default="", help="Pipe-separated paths to exclude")
    parser.add_argument("--dry-run", action="store_true", default=False)
    parser.add_argument("--confirm", action="store_true", default=False)
    args = parser.parse_args()

    tool_path = find_tool("slither")
    if not tool_path:
        print("[FAIL] 'slither' executable not found on PATH", file=sys.stderr)
        sys.exit(1)

    cmd = [tool_path, args.target, "--sarif", os.path.join(args.output_dir, "slither.sarif"), "--fail-none"]
    if args.exclude_paths:
        cmd.extend(["--filter-paths", args.exclude_paths])

    flags_to_check = ["--sarif", "--fail-none"]
    if args.exclude_paths:
        flags_to_check.append("--filter-paths")

    if not check_help_flags(tool_path, flags_to_check):
        sys.exit(1)

    if args.dry_run or not args.confirm:
        print(f"[DRY-RUN] Verified slither command: {' '.join(cmd)}")
        sys.exit(0)

    os.makedirs(args.output_dir, exist_ok=True)
    t0 = time.time()
    res = subprocess.run(cmd, capture_output=True, text=True)
    duration = time.time() - t0

    sarif_path = os.path.join(args.output_dir, "slither.sarif")
    sha256 = ""
    if os.path.exists(sarif_path):
        with open(sarif_path, "rb") as f:
            sha256 = hashlib.sha256(f.read()).hexdigest()

    receipt = {
        "tool": "slither",
        "command": cmd,
        "exit_code": res.returncode,
        "duration_seconds": duration,
        "sarif_file": sarif_path,
        "sha256": sha256
    }
    with open(os.path.join(args.output_dir, "receipt.json"), "w") as f:
        json.dump(receipt, f, indent=2)

    print(f"[OK] Slither executed in {duration:.2f}s, SHA-256: {sha256[:16]}...")

if __name__ == "__main__":
    main()
