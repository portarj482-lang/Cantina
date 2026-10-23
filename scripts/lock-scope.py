#!/usr/bin/env python3
"""
scripts/lock-scope.py
Computes LF-normalized scope hash and validates against snapshots/scope.sha256
consistent with universal_adaptive_engine/policies/scope_verifier.py.
Supports --check, --write, and --mode flags.
"""

import sys
import os
import hashlib
import argparse

def compute_scope_hashes(scope_path: str) -> dict[str, str]:
    if not os.path.exists(scope_path):
        raise FileNotFoundError(f"Scope file not found: {scope_path}")
        
    with open(scope_path, "rb") as f:
        content_bytes = f.read()

    # Exact byte hash (canonical scope_verifier.py standard)
    exact_hash = hashlib.sha256(content_bytes).hexdigest()

    # LF-normalized text hash
    content_text = content_bytes.decode("utf-8")
    content_lf = content_text.replace("\r\n", "\n")
    lf_hash = hashlib.sha256(content_lf.encode("utf-8")).hexdigest()

    # Marker-delimited block hash
    start_marker = "<!-- SCOPE START -->"
    end_marker = "<!-- SCOPE END -->"
    s_idx = content_lf.find(start_marker)
    e_idx = content_lf.find(end_marker)
    if s_idx != -1 and e_idx != -1:
        block = content_lf[s_idx:e_idx + len(end_marker)] + "\n"
        marker_hash = hashlib.sha256(block.encode("utf-8")).hexdigest()
    else:
        marker_hash = lf_hash

    return {
        "exact": exact_hash,
        "lf_normalized": lf_hash,
        "marker_block": marker_hash,
    }

def main():
    parser = argparse.ArgumentParser(description="Compute and verify scope.md SHA256 snapshot")
    parser.add_argument("--scope", default="bounties/base/scope.md", help="Path to scope.md")
    parser.add_argument("--snapshot", default="bounties/base/snapshots/scope.sha256", help="Path to scope.sha256")
    parser.add_argument("--write", action="store_true", help="Write hash to snapshot file")
    parser.add_argument("--check", action="store_true", help="Verify hash against snapshot file")
    args = parser.parse_args()

    hashes = compute_scope_hashes(args.scope)
    canonical_hash = hashes["exact"]
    print(f"Scope SHA-256 (Canonical byte hash): {canonical_hash}")
    print(f"Scope SHA-256 (LF-normalized hash):  {hashes['lf_normalized']}")

    if args.write:
        os.makedirs(os.path.dirname(args.snapshot), exist_ok=True)
        with open(args.snapshot, "w", encoding="utf-8") as f:
            f.write(canonical_hash + "\n")
        print(f"Updated {args.snapshot} with hash: {canonical_hash}")

    if args.check:
        if not os.path.exists(args.snapshot):
            print(f"FAILED: Snapshot {args.snapshot} does not exist.")
            sys.exit(1)
        with open(args.snapshot, "r", encoding="utf-8") as f:
            stored_h = f.read().strip()
        if canonical_hash == stored_h or hashes["lf_normalized"] == stored_h:
            print(f"PASSED: Scope hash matches snapshot ({stored_h}).")
            sys.exit(0)
        else:
            print(f"MISMATCH: Computed {canonical_hash} != Stored {stored_h}")
            sys.exit(1)

if __name__ == "__main__":
    main()
