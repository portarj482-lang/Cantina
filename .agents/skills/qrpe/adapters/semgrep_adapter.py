#!/usr/bin/env python3
"""
Semgrep Deterministic Adapter for QRPE.
Executes rules, collects JSON, and records cryptographic receipts.
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
    parser = argparse.ArgumentParser(description="QRPE Semgrep Adapter")
    parser.add_argument("--target", required=True, help="Target directory")
    parser.add_argument("--output-dir", required=True, help="Scan output directory")
    parser.add_argument("--config", default="auto", help="Rule config")
    parser.add_argument("--dry-run", action="store_true", default=False)
    parser.add_argument("--confirm", action="store_true", default=False)
    args = parser.parse_args()

    tool_path = find_tool("semgrep")
    if not tool_path:
        print("[FAIL] 'semgrep' executable not found on PATH", file=sys.stderr)
        sys.exit(1)

    out_file = os.path.join(args.output_dir, "semgrep.json")
    cmd = [tool_path, "--config", args.config, "--json", "-o", out_file, args.target]

    if args.dry_run or not args.confirm:
        print(f"[DRY-RUN] Verified semgrep command: {' '.join(cmd)}")
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
        "tool": "semgrep",
        "command": cmd,
        "exit_code": res.returncode,
        "duration_seconds": duration,
        "output_file": out_file,
        "sha256": sha256
    }
    with open(os.path.join(args.output_dir, "receipt.json"), "w") as f:
        json.dump(receipt, f, indent=2)

    print(f"[OK] Semgrep executed in {duration:.2f}s, SHA-256: {sha256[:16]}...")

if __name__ == "__main__":
    main()
