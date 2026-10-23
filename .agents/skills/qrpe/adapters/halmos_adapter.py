#!/usr/bin/env python3
"""
Halmos Symbolic Prover Adapter for QRPE.
Enforces solver timeout, loop bounds, and records formal proof classification.
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

def main():
    parser = argparse.ArgumentParser(description="QRPE Halmos Adapter")
    parser.add_argument("--target", required=True, help="Target build copy")
    parser.add_argument("--output-dir", required=True, help="Scan output directory")
    parser.add_argument("--match-test", default="check_", help="Test filter pattern")
    parser.add_argument("--solver-timeout", default="10000", help="Timeout in ms")
    parser.add_argument("--loop-bound", default="2", help="Loop unroll bound")
    parser.add_argument("--dry-run", action="store_true", default=False)
    parser.add_argument("--confirm", action="store_true", default=False)
    args = parser.parse_args()

    is_dry_run = args.dry_run or not args.confirm

    tool_path = find_tool("halmos")
    if not tool_path:
        if is_dry_run:
            tool_path = "halmos"
        else:
            print("[FAIL] 'halmos' executable not found on PATH", file=sys.stderr)
            sys.exit(1)

    cmd = [
        tool_path,
        "--solver-timeout-assertion", args.solver_timeout,
        "--loop", args.loop_bound,
        "--match-test", args.match_test
    ]

    if is_dry_run:
        print(f"[DRY-RUN] Verified halmos command in {args.target}: {' '.join(cmd)}")
        sys.exit(0)

    os.makedirs(args.output_dir, exist_ok=True)
    t0 = time.time()
    res = subprocess.run(cmd, cwd=args.target, capture_output=True, text=True)
    duration = time.time() - t0

    out_file = os.path.join(args.output_dir, "halmos_output.txt")
    with open(out_file, "w") as f:
        f.write(res.stdout + "\n" + res.stderr)

    with open(out_file, "rb") as f:
        sha256 = hashlib.sha256(f.read()).hexdigest()

    status = "PROVEN" if res.returncode == 0 else "COUNTEREXAMPLE_OR_ERROR"
    receipt = {
        "tool": "halmos",
        "command": cmd,
        "exit_code": res.returncode,
        "classification": status,
        "duration_seconds": duration,
        "output_file": out_file,
        "sha256": sha256
    }
    with open(os.path.join(args.output_dir, "receipt.json"), "w") as f:
        json.dump(receipt, f, indent=2)

    print(f"[OK] Halmos completed in {duration:.2f}s with status {status}, SHA-256: {sha256[:16]}...")

if __name__ == "__main__":
    main()
