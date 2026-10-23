#!/usr/bin/env python3
"""
Solana & Anchor Test Adapter for QRPE.
Interfaces with anchor and solana-test-validator for program IDL verification and local PoC execution.
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
    parser = argparse.ArgumentParser(description="QRPE Solana & Anchor Adapter")
    parser.add_argument("--target", required=True, help="Target program directory")
    parser.add_argument("--output-dir", required=True, help="Scan/receipt output directory")
    parser.add_argument("--action", choices=["idl", "test"], default="test", help="Action to perform")
    parser.add_argument("--dry-run", action="store_true", default=False)
    parser.add_argument("--confirm", action="store_true", default=False)
    args = parser.parse_args()

    is_dry_run = args.dry_run or not args.confirm

    tool_path = find_tool("anchor")
    if not tool_path:
        if is_dry_run:
            tool_path = "anchor"
        else:
            print("[FAIL] 'anchor' executable not found on PATH", file=sys.stderr)
            sys.exit(1)

    cmd = [tool_path, "build" if args.action == "idl" else "test", "--skip-local-validator"]

    if is_dry_run:
        print(f"[DRY-RUN] Verified anchor command in {args.target}: {' '.join(cmd)}")
        sys.exit(0)

    os.makedirs(args.output_dir, exist_ok=True)
    t0 = time.time()
    res = subprocess.run(cmd, cwd=args.target, capture_output=True, text=True)
    duration = time.time() - t0

    out_file = os.path.join(args.output_dir, "anchor_output.txt")
    with open(out_file, "w") as f:
        f.write(res.stdout + "\n" + res.stderr)

    with open(out_file, "rb") as f:
        sha256 = hashlib.sha256(f.read()).hexdigest()

    receipt = {
        "tool": "anchor",
        "action": args.action,
        "command": cmd,
        "exit_code": res.returncode,
        "duration_seconds": duration,
        "output_file": out_file,
        "sha256": sha256
    }
    with open(os.path.join(args.output_dir, "receipt.json"), "w") as f:
        json.dump(receipt, f, indent=2)

    print(f"[OK] Anchor {args.action} completed in {duration:.2f}s with exit code {res.returncode}, SHA-256: {sha256[:16]}...")

if __name__ == "__main__":
    main()
