#!/usr/bin/env python3
"""
Aderyn Deterministic Adapter for QRPE.
Verifies flags, captures JSON output, and computes SHA-256 digests.
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
    parser = argparse.ArgumentParser(description="QRPE Aderyn Adapter")
    parser.add_argument("--target", required=True, help="Target root directory")
    parser.add_argument("--output-dir", required=True, help="Scan output directory")
    parser.add_argument("--dry-run", action="store_true", default=False)
    parser.add_argument("--confirm", action="store_true", default=False)
    args = parser.parse_args()

    tool_path = find_tool("aderyn")
    if not tool_path:
        print("[FAIL] 'aderyn' executable not found on PATH", file=sys.stderr)
        sys.exit(1)

    out_file = os.path.join(args.output_dir, "aderyn.json")
    cmd = [tool_path, args.target, "--output", out_file]

    # Verify flags in help
    res = subprocess.run([tool_path, "--help"], capture_output=True, text=True)
    if "--output" not in res.stdout:
        print("[FAIL] Aderyn help check failed for required flags", file=sys.stderr)
        sys.exit(1)

    if args.dry_run or not args.confirm:
        print(f"[DRY-RUN] Verified aderyn command: {' '.join(cmd)}")
        sys.exit(0)

    os.makedirs(args.output_dir, exist_ok=True)
    t0 = time.time()
    res = subprocess.run(cmd, capture_output=True, text=True)
    duration = time.time() - t0

    sha256 = ""
    if os.path.exists(out_file):
        with open(out_file, "rb") as f:
            sha256 = hashlib.sha256(f.read()).hexdigest()

    receipt = {
        "tool": "aderyn",
        "command": cmd,
        "exit_code": res.returncode,
        "duration_seconds": duration,
        "output_file": out_file,
        "sha256": sha256
    }
    with open(os.path.join(args.output_dir, "receipt.json"), "w") as f:
        json.dump(receipt, f, indent=2)

    print(f"[OK] Aderyn executed in {duration:.2f}s, SHA-256: {sha256[:16]}...")

if __name__ == "__main__":
    main()
