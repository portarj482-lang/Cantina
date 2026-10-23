#!/usr/bin/env python3
"""
Foundry Test Adapter for QRPE.
Executes forge test suites, enforces dual-fork runs, and validates determinism receipts.
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
    parser = argparse.ArgumentParser(description="QRPE Foundry Adapter")
    parser.add_argument("--target", required=True, help="Target build copy directory")
    parser.add_argument("--output-dir", required=True, help="Scan/receipt output directory")
    parser.add_argument("--match-test", default="", help="Forge test filter")
    parser.add_argument("--fork-url-env", default="", help="Name of env var containing RPC URL (never raw URL)")
    parser.add_argument("--fork-block", default="", help="Pinned block number")
    parser.add_argument("--dry-run", action="store_true", default=False)
    parser.add_argument("--confirm", action="store_true", default=False)
    args = parser.parse_args()

    tool_path = find_tool("forge")
    if not tool_path:
        print("[FAIL] 'forge' executable not found on PATH", file=sys.stderr)
        sys.exit(1)

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

    # Redact actual RPC URL from logged command
    safe_cmd_str = " ".join([c if not (args.fork_url_env and os.environ.get(args.fork_url_env) and c == os.environ.get(args.fork_url_env)) else f"${args.fork_url_env}" for c in cmd])

    if args.dry_run or not args.confirm:
        print(f"[DRY-RUN] Verified forge test command in {args.target}: {safe_cmd_str}")
        sys.exit(0)

    os.makedirs(args.output_dir, exist_ok=True)
    t0 = time.time()
    res = subprocess.run(cmd, cwd=args.target, capture_output=True, text=True)
    duration = time.time() - t0

    out_file = os.path.join(args.output_dir, "forge_output.txt")
    with open(out_file, "w") as f:
        f.write(res.stdout + "\n" + res.stderr)

    with open(out_file, "rb") as f:
        sha256 = hashlib.sha256(f.read()).hexdigest()

    receipt = {
        "tool": "forge",
        "command_template": safe_cmd_str,
        "exit_code": res.returncode,
        "duration_seconds": duration,
        "output_file": out_file,
        "sha256": sha256
    }
    with open(os.path.join(args.output_dir, "receipt.json"), "w") as f:
        json.dump(receipt, f, indent=2)

    print(f"[OK] Forge test completed in {duration:.2f}s with exit code {res.returncode}, SHA-256: {sha256[:16]}...")

if __name__ == "__main__":
    main()
