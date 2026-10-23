#!/usr/bin/env python3
"""
Mythril Symbolic Execution Adapter for QRPE.
Invokes mythril with bounded execution depth and JSON report extraction.
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
    parser = argparse.ArgumentParser(description="QRPE Mythril Adapter")
    parser.add_argument("--contract", required=True, help="Target Solidity contract")
    parser.add_argument("--output-dir", required=True, help="Scan output directory")
    parser.add_argument("--max-depth", default="12", help="Max transaction depth")
    parser.add_argument("--dry-run", action="store_true", default=False)
    parser.add_argument("--confirm", action="store_true", default=False)
    args = parser.parse_args()

    tool_path = find_tool("myth")
    if not tool_path:
        print("[FAIL] 'myth' executable not found on PATH", file=sys.stderr)
        sys.exit(1)

    cmd = [tool_path, "analyze", args.contract, "--max-depth", args.max_depth, "-o", "json"]

    if args.dry_run or not args.confirm:
        print(f"[DRY-RUN] Verified mythril command: {' '.join(cmd)}")
        sys.exit(0)

    os.makedirs(args.output_dir, exist_ok=True)
    t0 = time.time()
    res = subprocess.run(cmd, capture_output=True, text=True)
    duration = time.time() - t0

    out_file = os.path.join(args.output_dir, "mythril.json")
    with open(out_file, "w") as f:
        f.write(res.stdout if res.stdout else res.stderr)

    with open(out_file, "rb") as f:
        sha256 = hashlib.sha256(f.read()).hexdigest()

    receipt = {
        "tool": "mythril",
        "command": cmd,
        "exit_code": res.returncode,
        "duration_seconds": duration,
        "output_file": out_file,
        "sha256": sha256
    }
    with open(os.path.join(args.output_dir, "receipt.json"), "w") as f:
        json.dump(receipt, f, indent=2)

    print(f"[OK] Mythril completed in {duration:.2f}s, SHA-256: {sha256[:16]}...")

if __name__ == "__main__":
    main()
