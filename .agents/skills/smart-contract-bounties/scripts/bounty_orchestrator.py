#!/usr/bin/env python3
"""bounty_orchestrator.py - Unified Smart Contract Bug Bounty Orchestration CLI.

Zero-dependency standard library CLI that unifies all smart contract bounty skills:
  - Platform governance & scope locking (Cantina marker-delimited block & generic LF normalization)
  - Skill routing & attack vector selection across specialized domains
  - Disciplined 5-beat hypothesis cycle (Read-Predict-Probe-Prove/Kill-Record)
  - Strictly append-only audit ledgers adhering to GEMINI.md Part 5 Rule 5.3
  - Foundry PoC structural quality auditing (8 non-negotiables)
  - 6-Gate readiness auditing with substantive sentence-level provenance checks
  - Retrospective learning, kill taxonomy analytics, and severity calibration

Usage:
  py -3 bounty_orchestrator.py route --target <file.sol|directory|text>
  py -3 bounty_orchestrator.py execution-matrix [--bounty-root <dir>] [--output <matrix.json>]
  py -3 bounty_orchestrator.py evidence-seal --output <manifest.json>
  py -3 bounty_orchestrator.py evidence-verify --manifest <manifest.json>
  py -3 bounty_orchestrator.py continuity-audit [--output <report.json>]
  py -3 bounty_orchestrator.py run-record --stage <name> --status <status> [--artifact <path>]
  py -3 bounty_orchestrator.py run-verify
  py -3 bounty_orchestrator.py run-observe [--window <count>]
  py -3 bounty_orchestrator.py telemetry-report [--output <report.json>]
  py -3 bounty_orchestrator.py workflow-preflight [--finding <F-001.md>] [--output <report.json>]
  py -3 bounty_orchestrator.py scope-lock [--scope-file <path>] [--snapshot-file <path>]
  py -3 bounty_orchestrator.py scope-verify [--scope-file <path>] [--snapshot-file <path>]
  py -3 bounty_orchestrator.py hyp-add --id H-001 --target "Vault.withdraw" --actor "unprivileged" --prediction "reverts with InsufficientBalance"
  py -3 bounty_orchestrator.py hyp-status --id H-001 --status killed --category "reentrancy-guard" --reason "protected by nonReentrant"
  py -3 bounty_orchestrator.py hyp-list [--status pending|proved|killed|inconclusive]
  py -3 bounty_orchestrator.py kills
  py -3 bounty_orchestrator.py lesson-add --id L-001 --text "..." [--tags tag1,tag2]
  py -3 bounty_orchestrator.py lesson-list
  py -3 bounty_orchestrator.py outcome-add --id F-001 --predicted High --actual Medium [--notes "..."]
  py -3 bounty_orchestrator.py calibrate
  py -3 bounty_orchestrator.py poc-audit --poc-file <test.t.sol>
  py -3 bounty_orchestrator.py gate-audit --finding <F-001.md> [--bounty-root <dir>]
  py -3 bounty_orchestrator.py learn-summary
"""

import argparse
import contextlib
import datetime
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

# Fix Windows console encoding if needed
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# --- Constants & Regexes ---
PROVENANCE_TAG_RE = re.compile(
    r"\[(SRC|LOCAL|TOOL|POC|WEB|USER|ASSUMPTION|UNKNOWN)(?::[^\]]+)?\]"
)
SRC_TAG_RE = re.compile(r"\[SRC:\s*([^:\s]+):(\d+(?:-\d+)?)\s*@([0-9a-fA-F]{7,40})\]")
POC_TAG_RE = re.compile(r"\[POC:\s*(PASS|FAIL)[^\]]*\]", re.I)

BARE_EXPECT_REVERT = re.compile(r"vm\.expectRevert\s*\(\s*\)\s*;")
SPECIFIC_EXPECT_REVERT = re.compile(r"vm\.expectRevert\s*\([^;)]+\)\s*;")
FORK_PIN_PATTERN = re.compile(r"(createSelectFork|selectFork|createFork|rollFork|--fork-block-number|\bforkBlock\b)", re.I)
UNPRIVILEGED_ACTOR_PATTERN = re.compile(r'(makeAddr\s*\(\s*["\']attacker["\']|makeAddr\s*\(\s*["\']user["\']|startPrank|vm\.prank)', re.I)
DELTA_ASSERT_PATTERN = re.compile(
    r"\b(assertEq|assertApproxEqAbs|assertApproxEqRel|assertLt|assertGt|assertTrue|assertFalse|assertGe|assertLe)\s*\([^;]*(?:delta|diff|balanceAfter\s*-\s*balanceBefore|vaultBefore\s*-\s*vaultAfter|stolenAmount|stolen|drain|drained|profit|loss)\b",
    re.I,
)
META_BULLET_RE = re.compile(
    r"^-\s*\*\*(?:Status|Bounty|Commit|Severity|PoC|Gate pass rate|Open questions|Submission ID|Change log):",
    re.I,
)

SECRET_PATTERNS = [
    re.compile(r"alch_[A-Za-z0-9]{8,}"),
    re.compile(r"rnd_[A-Za-z0-9]{8,}"),
    re.compile(
        r"https?://[^\s\"']*(alchemy|infura|quiknode|drpc)[^\s\"']*/[A-Za-z0-9_\-]{16,}",
        re.I,
    ),
    re.compile(r"\b0x[0-9a-fA-F]{64}\b"),  # 64-hex private key candidate
]

def strip_solidity_comments(source: str) -> str:
    """Strip single-line and multi-line comments from Solidity code."""
    no_block = re.sub(r"/\*.*?\*/", "", source, flags=re.DOTALL)
    no_line = re.sub(r"//[^\r\n]*", "", no_block)
    return no_line


REQUIRED_ENVELOPE_FIELDS = [
    "agent",
    "stage",
    "status",
    "thought",
    "plan",
    "evidence",
    "result_files",
    "stop_reason",
]
VALID_ENVELOPE_STATUSES = {
    "ok",
    "fail",
    "tool_missing",
    "stopped",
    "skipped",
    "no_tests",
}
VALID_EVIDENCE_TYPES = {
    "SRC",
    "LOCAL",
    "TOOL",
    "POC",
    "WEB",
    "USER",
    "ASSUMPTION",
    "UNKNOWN",
}
HEX40_RE = re.compile(r"^[0-9a-fA-F]{40}$")
HEX64_RE = re.compile(r"^[0-9a-fA-F]{64}$")
SRC_PATH_RE = re.compile(r"^[^:\s]+:\d+$")

DOMAIN_KEYWORDS = {
    "eip7702": ["7702", "0xef0100", "authorization", "isvalidsignature", "multiauth", "delegatedaccount", "delegation"],
    "erc4337": ["4337", "useroperation", "paymaster", "entrypoint", "postop", "validateuserop", "validatuserop", "magicspend"],
    "transient": ["tstore", "tload", "transient", "eip1153", "1153"],
    "uniswap_v4": ["hook", "poolmanager", "unlock", "beforeswap", "afterswap", "beforemint", "modifyposition", "beforeswapdelta"],
    "lending": ["liquidate", "collateral", "borrow", "debt", "interestrate", "shareprice", "healthfactor", "ltv", "bad debt", "repay"],
    "oracle": ["pyth", "chainlink", "twap", "latestrounddata", "consult", "sequencer", "stale", "minanswer", "maxanswer"],
}

# --- Helper Functions ---

def get_active_bounty_slug() -> str | None:
    """Detect active bounty slug from MEMORY.md if present."""
    memory_file = Path("MEMORY.md")
    if memory_file.is_file():
        try:
            content = memory_file.read_text(encoding="utf-8")
            match = re.search(r"^Active bounty:\s*([^\r\n]+)", content, re.MULTILINE)
            if match:
                slug = match.group(1).strip()
                if slug and slug.lower() != "none":
                    return slug
        except Exception:
            pass
    return None

def resolve_bounty_root(custom_root: str | None = None) -> Path:
    """Resolve bounty root path prioritizing user input, active bounty, or local directory."""
    if custom_root and custom_root != ".":
        return Path(custom_root).resolve()
    slug = get_active_bounty_slug()
    if slug:
        bounty_dir = Path("bounties") / slug
        if bounty_dir.is_dir():
            return bounty_dir.resolve()
    return Path(".").resolve()

def resolve_ledger_file(custom_ledger: str | None = None) -> Path:
    """Resolve hypothesis ledger file adhering to GEMINI.md focus locking."""
    if custom_ledger:
        return Path(custom_ledger).resolve()
    slug = get_active_bounty_slug()
    if slug:
        p = Path("bounties") / slug / "logs" / "hypotheses.jsonl"
        return p.resolve()
    return Path(".audit_learn/hypotheses.jsonl").resolve()

def resolve_lessons_file(custom_file: str | None = None) -> Path:
    """Resolve lessons file adhering to global/active bounty layout."""
    if custom_file:
        return Path(custom_file).resolve()
    p = Path("global/lessons.md")
    if p.parent.is_dir():
        return p.resolve()
    return Path(".audit_learn/lessons.jsonl").resolve()

def normalize_lf(data: bytes) -> bytes:
    """Normalize CRLF and CR to LF."""
    return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")

def extract_normalized_scope(scope_file: Path) -> tuple[bytes, str]:
    """Extract scope content and hash.
    
    If Cantina marker comments <!-- SCOPE START --> and <!-- SCOPE END --> are present,
    hashes the slice between them inclusive (with trailing newline and LF normalization).
    Otherwise, hashes the full file with LF normalization.
    """
    if not scope_file.is_file():
        raise FileNotFoundError(f"Scope file not found: {scope_file}")

    raw_bytes = scope_file.read_bytes()
    normalized = normalize_lf(raw_bytes)
    start_marker = b"<!-- SCOPE START -->"
    end_marker = b"<!-- SCOPE END -->"

    lines = normalized.splitlines(keepends=True)
    starts = [i for i, line in enumerate(lines) if line.strip() == start_marker]
    ends = [i for i, line in enumerate(lines) if line.strip() == end_marker]

    if len(starts) == 1 and len(ends) == 1 and starts[0] < ends[0]:
        scope_slice = b"".join(lines[starts[0] : ends[0] + 1])
        if not scope_slice.endswith(b"\n"):
            scope_slice += b"\n"
        digest = hashlib.sha256(scope_slice).hexdigest()
        return scope_slice, digest

    # If markers not present, hash full normalized text
    if not normalized.endswith(b"\n"):
        normalized += b"\n"
    digest = hashlib.sha256(normalized).hexdigest()
    return normalized, digest

# --- Subcommand Handlers ---

def cmd_route(args: argparse.Namespace) -> int:
    target = args.target or ""
    search_space = target.lower()

    target_path = Path(target)
    if target_path.is_file():
        try:
            content = target_path.read_text(encoding="utf-8", errors="ignore").lower()
            search_space += " " + content
        except Exception as e:
            print(f"[WARN] Could not read target file: {e}")
    elif target_path.is_dir():
        # Recursively search .sol files in target directory
        try:
            collected = []
            for sol_file in target_path.rglob("*.sol"):
                try:
                    collected.append(sol_file.read_text(encoding="utf-8", errors="ignore").lower())
                except Exception:
                    pass
            search_space += " " + " ".join(collected)
        except Exception as e:
            print(f"[WARN] Error scanning directory {target_path}: {e}")

    matched_domains = []
    for domain, kws in DOMAIN_KEYWORDS.items():
        if any(kw in search_space for kw in kws):
            matched_domains.append(domain)

    print("===============================================================")
    print("[*] SMART CONTRACT BOUNTY ROUTER: RECOMMENDED WORKFLOW")
    print("---------------------------------------------------------------")
    print("1. Core Pipeline Orchestration:")
    print("   * Platform Intake: Enforce 'cantina-bug-bounty' or 'bug-bounty' scope lock")
    print("   * Hypothesis Loop: Enforce 5-beat 'v4lend-hypothesis-cycle'")
    print("   * PoC Engineering: Enforce 'foundry-poc-writing' 8 non-negotiables")
    print("   * Retrospective: Run 'audit-retrospective' learning loop & pre-PoC filters")
    print("---------------------------------------------------------------")
    if matched_domains:
        print("2. Detected Specialized Domain Skills to Activate:")
        for dom in matched_domains:
            if dom == "eip7702":
                print("   [+] EIP-7702 Delegation Audit (eip-7702-smart-account-audit):")
                print("       - ERC-1271 fallback risks, cross-chain replay tuples (chainId=0), address aliasing")
            elif dom == "erc4337":
                print("   [+] ERC-4337 Paymaster Audit (erc4337-paymaster-accounting):")
                print("       - validatePaymasterUserOp storage invariants, postOp gas griefing, MagicSpend allowances")
            elif dom == "transient":
                print("   [+] EIP-1153 Transient Storage (transient-storage-lifecycle):")
                print("       - TSTORE/TLOAD cleanup, multicall reentrancy guard reset failures, transient allowances")
            elif dom == "uniswap_v4":
                print("   [+] Uniswap v4 Hook Security:")
                print("       - PoolManager unlock callbacks, BeforeSwapDelta settlement, dynamic fee manipulation")
            elif dom == "lending":
                print("   [+] Lending Protocol Invariants:")
                print("       - Bad debt socialization, liquidation frontrunning, share price dilution/inflation")
            elif dom == "oracle":
                print("   [+] Oracle & Pricing Feeds:")
                print("       - Staleness, sequencer downtime check, minAnswer/maxAnswer bounds, single-block TWAPs")
    else:
        print("2. Standard EVM Audit Vectors Activated:")
        print("   * Access control, Reentrancy, Token Assumptions (ERC-777/fee-on-transfer), Precision/Rounding.")
    print("===============================================================")
    return 0

def cmd_execution_matrix(args: argparse.Namespace) -> int:
    """Summarize bounty progress from local artifacts and repository checkouts."""
    bounty_root = resolve_bounty_root(getattr(args, "bounty_root", None))
    if not bounty_root.is_dir():
        print(f"[FAIL] Bounty directory not found: {bounty_root}", file=sys.stderr)
        return 1

    scope_file = bounty_root / "scope.md"
    snapshot_file = bounty_root / "snapshots" / "scope.sha256"
    scope_status = "missing"
    scope_digest = None
    if scope_file.is_file() and snapshot_file.is_file():
        try:
            expected = snapshot_file.read_text(encoding="utf-8").strip().split()[0].lower()
            _, scope_digest = extract_normalized_scope(scope_file)
            scope_status = "locked" if expected == scope_digest.lower() else "mismatch"
        except (OSError, ValueError, IndexError):
            scope_status = "invalid"
            scope_digest = None

    repositories = []
    for child in sorted(bounty_root.iterdir()):
        if not child.is_dir() or not (child / ".git").exists():
            continue
        try:
            result = subprocess.run(
                ["git", "-C", str(child), "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                check=False,
                timeout=5,
            )
            revision = result.stdout.strip() if result.returncode == 0 else None
        except (OSError, subprocess.TimeoutExpired):
            revision = None
        repositories.append({"name": child.name, "path": str(child), "head": revision})

    facts_file = bounty_root / "facts.md"
    ledger_file = bounty_root / "logs" / "hypotheses.jsonl"
    findings_dir = bounty_root / "findings"
    poc_dir = bounty_root / "poc"
    scans_dir = bounty_root / "scans"
    state_file = bounty_root / "state.md"

    def file_count(directory: Path, pattern: str) -> int:
        return sum(1 for item in directory.rglob(pattern) if item.is_file()) if directory.is_dir() else 0

    finding_count = file_count(findings_dir, "F-*.md")
    poc_count = file_count(poc_dir, "*.t.sol")
    scan_count = file_count(scans_dir, "*")
    hypothesis_count = 0
    if ledger_file.is_file():
        try:
            hypothesis_count = sum(
                1 for line in ledger_file.read_text(encoding="utf-8").splitlines() if line.strip()
            )
        except OSError:
            pass

    phase = None
    if state_file.is_file():
        state_text = state_file.read_text(encoding="utf-8", errors="replace")
        match = re.search(r"^Phase:\s*(.+)$", state_text, re.MULTILINE)
        phase = match.group(1).strip() if match else None

    stages = [
        {"stage": "scope", "status": scope_status, "sha256": scope_digest},
        {"stage": "reconnaissance", "status": "present" if repositories else "missing", "repositories": len(repositories), "facts_file": facts_file.is_file()},
        {"stage": "analysis", "status": "present" if hypothesis_count or finding_count else "not_started", "hypotheses": hypothesis_count, "findings": finding_count},
        {"stage": "reproduction", "status": "present" if poc_count else "not_started", "poc_tests": poc_count, "scan_artifacts": scan_count},
        {"stage": "reporting", "status": "present" if finding_count else "not_started", "findings": finding_count},
    ]
    matrix = {
        "bounty_root": str(bounty_root),
        "phase": phase,
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "stages": stages,
        "repositories": repositories,
        "note": "Artifact presence is reported; it does not establish that findings are valid or tests passed.",
    }

    print(f"Execution matrix: {bounty_root}")
    print(f"Current phase: {phase or 'unknown'}")
    for stage in stages:
        print(f"[{stage['status'].upper()}] {stage['stage']}")
    print(
        f"Repositories: {len(repositories)} | Hypothesis records: {hypothesis_count} | "
        f"Findings: {finding_count} | PoC tests: {poc_count} | Scan artifacts: {scan_count}"
    )

    output = getattr(args, "output", None)
    if output:
        output_path = Path(output).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(matrix, indent=2), encoding="utf-8")
        print(f"JSON report: {output_path}")
    return 1 if scope_status in {"mismatch", "invalid"} else 0


def evidence_inventory(bounty_root: Path) -> list[dict[str, str]]:
    """Hash first-party bounty evidence only; never follow symlinks."""
    candidates = [bounty_root / "scope.md", bounty_root / "facts.md"]
    for dirname in ("findings", "scans", "poc"):
        directory = bounty_root / dirname
        if directory.is_dir():
            candidates.extend(path for path in directory.rglob("*") if path.is_file() and not path.is_symlink())

    entries = []
    for path in sorted(set(candidates)):
        if not path.is_file() or path.is_symlink():
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        entries.append({"path": path.relative_to(bounty_root).as_posix(), "sha256": digest})
    return entries


def evidence_merkle_root(entries: list[dict[str, str]]) -> str:
    """Build a domain-separated SHA-256 Merkle root from sorted path/hash entries."""
    leaves = [
        hashlib.sha256(
            b"leaf\0" + entry["path"].encode("utf-8") + b"\0" + bytes.fromhex(entry["sha256"])
        ).digest()
        for entry in entries
    ]
    if not leaves:
        return hashlib.sha256(b"empty\0").hexdigest()
    while len(leaves) > 1:
        if len(leaves) % 2:
            leaves.append(leaves[-1])
        leaves = [
            hashlib.sha256(b"node\0" + leaves[index] + leaves[index + 1]).digest()
            for index in range(0, len(leaves), 2)
        ]
    return leaves[0].hex()


def cmd_evidence_seal(args: argparse.Namespace) -> int:
    bounty_root = resolve_bounty_root(getattr(args, "bounty_root", None))
    if not bounty_root.is_dir():
        print(f"[FAIL] Bounty directory not found: {bounty_root}", file=sys.stderr)
        return 1
    try:
        entries = evidence_inventory(bounty_root)
    except OSError as exc:
        print(f"[FAIL] Could not read evidence inventory: {exc}", file=sys.stderr)
        return 1

    manifest = {
        "version": 1,
        "algorithm": "sha256-merkle-v1",
        "bounty_root": str(bounty_root),
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "entries": entries,
        "merkle_root": evidence_merkle_root(entries),
        "coverage": ["scope.md", "facts.md", "findings/", "scans/", "poc/"],
    }
    output_path = Path(args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"[OK] Sealed {len(entries)} evidence files.")
    print(f"     Merkle root: {manifest['merkle_root']}")
    print(f"     Manifest: {output_path}")
    return 0


def cmd_evidence_verify(args: argparse.Namespace) -> int:
    bounty_root = resolve_bounty_root(getattr(args, "bounty_root", None))
    if not bounty_root.is_dir():
        print(f"[FAIL] Bounty directory not found: {bounty_root}", file=sys.stderr)
        return 1
    manifest_path = Path(args.manifest).resolve()
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if not isinstance(manifest, dict):
            raise ValueError("manifest root must be a JSON object")
        if manifest.get("version") != 1 or manifest.get("algorithm") != "sha256-merkle-v1":
            raise ValueError("unsupported evidence manifest format")
        sealed_entries = manifest["entries"]
        if not isinstance(sealed_entries, list):
            raise ValueError("manifest entries must be a JSON array")
        current_entries = evidence_inventory(bounty_root)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"[FAIL] Cannot verify evidence manifest: {exc}", file=sys.stderr)
        return 1

    current_root = evidence_merkle_root(current_entries)
    entries_match = sealed_entries == current_entries
    root_matches = manifest.get("merkle_root") == current_root
    if entries_match and root_matches:
        print(f"[OK] Evidence manifest verified: {current_root}")
        print(f"     Files: {len(current_entries)}")
        return 0

    print("[FAIL] Evidence changed since it was sealed.", file=sys.stderr)
    print(f"       Sealed root:  {manifest.get('merkle_root')}", file=sys.stderr)
    print(f"       Current root: {current_root}", file=sys.stderr)
    return 1


RUN_LEDGER_GENESIS = "0" * 64
RUN_LEDGER_FIELDS = {"sequence", "timestamp", "bounty", "stage", "status", "artifact", "artifact_sha256", "previous_hash", "entry_hash"}


def _run_entry_hash(entry: dict) -> str:
    payload = {key: value for key, value in entry.items() if key != "entry_hash"}
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _verify_run_ledger(
    ledger_file: Path,
    bounty_root: Path | None = None,
    entries: list | None = None,
) -> tuple[int, str | None]:
    """Verify a hash-chained JSONL execution ledger; reject malformed history."""
    if not ledger_file.exists():
        return 0, None
    previous_hash = RUN_LEDGER_GENESIS
    count = 0
    try:
        with ledger_file.open("r", encoding="utf-8") as stream:
            for line_number, line in enumerate(stream, 1):
                if not line.endswith("\n"):
                    return count, f"line {line_number} is incomplete"
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    return count, f"line {line_number} is invalid JSON"
                if not isinstance(entry, dict) or set(entry) != RUN_LEDGER_FIELDS:
                    return count, f"line {line_number} has an invalid schema"
                if (
                    not isinstance(entry["sequence"], int)
                    or not isinstance(entry["timestamp"], str)
                    or not isinstance(entry["bounty"], str)
                    or not isinstance(entry["stage"], str)
                    or not isinstance(entry["status"], str)
                    or entry["status"] not in VALID_ENVELOPE_STATUSES
                    or (entry["artifact"] is not None and not isinstance(entry["artifact"], str))
                    or (entry["artifact_sha256"] is not None and not isinstance(entry["artifact_sha256"], str))
                    or ((entry["artifact"] is None) != (entry["artifact_sha256"] is None))
                    or (entry["status"] == "ok" and entry["artifact"] is None)
                ):
                    return count, f"line {line_number} has invalid field values"
                if entry["sequence"] != count + 1 or entry["previous_hash"] != previous_hash:
                    return count, f"line {line_number} breaks sequence or hash linkage"
                if not isinstance(entry["entry_hash"], str) or entry["entry_hash"] != _run_entry_hash(entry):
                    return count, f"line {line_number} has an invalid entry hash"
                if bounty_root is not None:
                    if entry["bounty"] != bounty_root.name:
                        return count, f"line {line_number} names a different bounty"
                    if entry["artifact"] is not None:
                        candidate = (bounty_root / entry["artifact"]).resolve()
                        try:
                            candidate.relative_to(bounty_root.resolve())
                        except ValueError:
                            return count, f"line {line_number} artifact escapes the bounty"
                        if not candidate.is_file() or hashlib.sha256(candidate.read_bytes()).hexdigest() != entry["artifact_sha256"]:
                            return count, f"line {line_number} artifact is missing or changed"
                    elif entry["artifact_sha256"] is not None:
                        return count, f"line {line_number} has a digest without an artifact"
                previous_hash = entry["entry_hash"]
                count += 1
                if entries is not None:
                    entries.append(entry)
    except OSError as exc:
        return count, f"cannot read ledger: {exc}"
    return count, None


def cmd_run_record(args: argparse.Namespace) -> int:
    """Append a manual stage record with an optional in-bounty artifact digest."""
    bounty_root = resolve_bounty_root()
    if not get_active_bounty_slug():
        print("[FAIL] No active bounty; refusing to create an execution record.", file=sys.stderr)
        return 1
    if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,64}", args.stage):
        print("[FAIL] Stage must be 1-64 letters, digits, or . _ : - characters.", file=sys.stderr)
        return 1
    if args.status == "ok" and not args.artifact:
        print("[FAIL] An artifact is required when status is 'ok'.", file=sys.stderr)
        return 1

    artifact_rel = None
    artifact_digest = None
    if args.artifact:
        supplied = Path(args.artifact)
        if supplied.is_absolute():
            print("[FAIL] Artifact path must be relative to the active bounty.", file=sys.stderr)
            return 1
        artifact_path = (bounty_root / supplied).resolve()
        try:
            artifact_rel = artifact_path.relative_to(bounty_root.resolve()).as_posix()
        except ValueError:
            print("[FAIL] Artifact must remain inside the active bounty.", file=sys.stderr)
            return 1
        if (bounty_root / supplied).is_symlink() or not artifact_path.is_file():
            print("[FAIL] Artifact must be an existing regular file, not a symlink.", file=sys.stderr)
            return 1
        artifact_digest = hashlib.sha256(artifact_path.read_bytes()).hexdigest()

    ledger_file = bounty_root / "logs" / "execution_ledger.jsonl"
    count, error = _verify_run_ledger(ledger_file, bounty_root)
    if error:
        print(f"[FAIL] Execution ledger integrity error: {error}", file=sys.stderr)
        return 1
    entry = {
        "sequence": count + 1,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "bounty": bounty_root.name,
        "stage": args.stage,
        "status": args.status,
        "artifact": artifact_rel,
        "artifact_sha256": artifact_digest,
        "previous_hash": RUN_LEDGER_GENESIS,
        "entry_hash": "",
    }
    if count:
        with ledger_file.open("r", encoding="utf-8") as stream:
            last_entry = json.loads(list(stream)[-1])
        entry["previous_hash"] = last_entry["entry_hash"]
    entry["entry_hash"] = _run_entry_hash(entry)
    ledger_file.parent.mkdir(parents=True, exist_ok=True)
    with ledger_file.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(entry, sort_keys=True, ensure_ascii=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    print(f"[OK] Recorded {args.stage}={args.status} (entry {entry['sequence']}, {entry['entry_hash'][:12]}).")
    return 0


def cmd_run_verify(args: argparse.Namespace) -> int:
    if not get_active_bounty_slug():
        print("[FAIL] No active bounty; cannot resolve the execution ledger.", file=sys.stderr)
        return 1
    bounty_root = resolve_bounty_root()
    ledger_file = bounty_root / "logs" / "execution_ledger.jsonl"
    count, error = _verify_run_ledger(ledger_file, bounty_root)
    if error:
        print(f"[FAIL] Execution ledger integrity error: {error}", file=sys.stderr)
        return 1
    print(f"[OK] Execution ledger verified: {count} entr{'y' if count == 1 else 'ies'}.")
    return 0


def cmd_run_observe(args: argparse.Namespace) -> int:
    """Summarize recent ledger outcomes and flag repeated operational failures."""
    if not get_active_bounty_slug():
        print("[FAIL] No active bounty; cannot resolve the execution ledger.", file=sys.stderr)
        return 1
    bounty_root = resolve_bounty_root()
    entries = []
    count, error = _verify_run_ledger(
        bounty_root / "logs" / "execution_ledger.jsonl", bounty_root, entries
    )
    if error:
        print(f"[FAIL] Execution ledger integrity error: {error}", file=sys.stderr)
        return 1
    if not entries:
        print("[NO DATA] No execution stages have been recorded.")
        return 0

    recent = entries[-args.window:]
    unhealthy = {"fail", "tool_missing", "stopped"}
    bad_count = sum(entry["status"] in unhealthy for entry in recent)
    streak = 0
    for entry in reversed(recent):
        if entry["status"] not in unhealthy:
            break
        streak += 1
    flags = []
    if streak >= 3:
        flags.append(f"{streak} consecutive unsuccessful stages")
    if len(recent) >= 4 and bad_count / len(recent) >= 0.5:
        flags.append(f"{bad_count}/{len(recent)} recent stages unsuccessful")
    print(f"Run observer: {bounty_root.name}; window={len(recent)}/{count}")
    print(f"Unsuccessful: {bad_count}; latest: {recent[-1]['stage']}={recent[-1]['status']}")
    if flags:
        for flag in flags:
            print(f"[ATTENTION] {flag}")
        print("No automatic recovery was attempted.")
        return 1
    print("[OK] No repeated-failure threshold reached.")
    return 0


def cmd_telemetry_report(args: argparse.Namespace) -> int:
    """Emit privacy-minimized local workflow metrics; never transmits data."""
    slug = get_active_bounty_slug()
    if not slug:
        print("[FAIL] No active bounty; telemetry report requires an active bounty.", file=sys.stderr)
        return 1
    bounty_root = resolve_bounty_root()
    run_entries = []
    run_count, run_error = _verify_run_ledger(
        bounty_root / "logs" / "execution_ledger.jsonl", bounty_root, run_entries
    )
    if run_error:
        print(f"[FAIL] Refusing telemetry export: execution ledger integrity error: {run_error}", file=sys.stderr)
        return 1

    run_statuses = {}
    stages = {}
    for entry in run_entries:
        status = entry["status"]
        run_statuses[status] = run_statuses.get(status, 0) + 1
        stage_counts = stages.setdefault(entry["stage"], {})
        stage_counts[status] = stage_counts.get(status, 0) + 1

    hyp_file = bounty_root / "logs" / "hypotheses.jsonl"
    hypotheses = {}
    if hyp_file.is_file():
        try:
            for line_number, line in enumerate(hyp_file.read_text(encoding="utf-8").splitlines(), 1):
                if not line.strip():
                    continue
                event = json.loads(line)
                if not isinstance(event, dict) or not isinstance(event.get("id"), str) or not event["id"]:
                    raise ValueError(f"hypothesis ledger line {line_number} has invalid shape")
                event_type = event.get("type")
                if event_type == "HYPOTHESIS_CREATED":
                    if event.get("status", "pending") not in {"pending", "proved", "killed", "inconclusive"}:
                        raise ValueError(f"hypothesis ledger line {line_number} has invalid status")
                    hypotheses[event["id"]] = {"status": event.get("status", "pending")}
                elif event_type == "HYPOTHESIS_STATUS_UPDATE" and event["id"] in hypotheses:
                    if event.get("status") not in {"pending", "proved", "killed", "inconclusive"}:
                        raise ValueError(f"hypothesis ledger line {line_number} has invalid status")
                    hypotheses[event["id"]]["status"] = event.get("status", "pending")
                else:
                    raise ValueError(f"hypothesis ledger line {line_number} has an unknown event")
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
            print(f"[FAIL] Refusing telemetry export: {exc}", file=sys.stderr)
            return 1

    hypothesis_statuses = {}
    for item in hypotheses.values():
        status = item["status"]
        hypothesis_statuses[status] = hypothesis_statuses.get(status, 0) + 1

    facts_file = bounty_root / "facts.md"
    facts_text = facts_file.read_text(encoding="utf-8", errors="replace") if facts_file.is_file() else ""
    fact_records = list(re.finditer(r"(?ms)^-\s*FACT-\d+:\s*(.*?)(?=^-\s*FACT-\d+:|\Z)", facts_text))
    facts_with_provenance = sum(bool(PROVENANCE_TAG_RE.search(match.group(1))) for match in fact_records)

    scope_status = "missing"
    scope_file = bounty_root / "scope.md"
    snapshot_file = bounty_root / "snapshots" / "scope.sha256"
    if scope_file.is_file() and snapshot_file.is_file():
        try:
            expected = snapshot_file.read_text(encoding="utf-8").strip().split()[0].lower()
            _, actual = extract_normalized_scope(scope_file)
            scope_status = "locked" if expected == actual.lower() else "mismatch"
        except (OSError, ValueError, IndexError):
            scope_status = "invalid"

    report = {
        "schema_version": 1,
        "bounty": slug,
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "scope_status": scope_status,
        "execution": {"ledger_integrity": "verified", "records": run_count, "status_counts": run_statuses, "stage_counts": stages},
        "hypotheses": {"unique_count": len(hypotheses), "status_counts": hypothesis_statuses},
        "facts": {"count": len(fact_records), "with_provenance": facts_with_provenance},
        "privacy": "Aggregate counts only; no raw claims, hypothesis targets, source paths, or credentials. Local output only; no network transmission.",
    }
    if args.output:
        output_path = Path(args.output).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"Telemetry report saved: {output_path}")
    print(
        f"Telemetry: scope={scope_status}; runs={run_count}; hypotheses={len(hypotheses)}; "
        f"facts={len(fact_records)} ({facts_with_provenance} sourced)."
    )
    return 1 if scope_status in {"missing", "mismatch", "invalid"} else 0


def cmd_workflow_preflight(args: argparse.Namespace) -> int:
    """Consolidate read-only continuity, memory, and optional finding checks."""
    slug = get_active_bounty_slug()
    if not slug:
        print("[FAIL] No active bounty; preflight requires an active bounty.", file=sys.stderr)
        return 1
    bounty_root = resolve_bounty_root()
    if args.finding and not Path(args.finding).is_file():
        print(f"[FAIL] Finding file not found: {args.finding}", file=sys.stderr)
        return 1

    try:
        with tempfile.TemporaryDirectory(prefix="cantina-preflight-") as temp_dir:
            temp_root = Path(temp_dir)
            continuity_path = temp_root / "continuity.json"
            facts_path = temp_root / "facts.json"
            finding_path = temp_root / "finding.json"
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                continuity_rc = cmd_continuity_audit(argparse.Namespace(output=str(continuity_path)))
                fact_rc = cmd_fact_review(argparse.Namespace(bounty_root=str(bounty_root), output=str(facts_path)))
                continuity = json.loads(continuity_path.read_text(encoding="utf-8"))
                fact_review = json.loads(facts_path.read_text(encoding="utf-8"))
                finding_report = None
                finding_rc = 0
                if args.finding:
                    finding_rc = cmd_gate_audit(argparse.Namespace(
                        finding=args.finding, bounty_root=str(bounty_root), output=str(finding_path)
                    ))
                    finding_report = json.loads(finding_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"[FAIL] Preflight could not produce a complete report: {exc}", file=sys.stderr)
        return 1

    continuity_ok = continuity_rc == 0 and all(
        section.get("status") == "ok"
        for section in (continuity.get("identity", {}), continuity.get("continuity", {}),
                        continuity.get("memory", {}), continuity.get("stability", {}))
    )
    facts_ok = fact_rc == 0
    finding_ok = finding_report is None or (
        finding_rc == 0 and finding_report.get("disposition") == "HUMAN_REVIEW_REQUIRED"
    )
    blockers = []
    if not continuity_ok:
        blockers.append("continuity checks need review")
    if not facts_ok:
        blockers.append("fact-memory review found items to resolve")
    if not finding_ok:
        blockers.append("finding readiness gates are incomplete")
    if blockers:
        disposition = "HOLD"
    elif finding_report:
        disposition = "HUMAN_REVIEW_REQUIRED"
    else:
        disposition = "FINDING_AUDIT_REQUIRED"

    report = {
        "schema_version": 1,
        "bounty": slug,
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "disposition": disposition,
        "authorization_granted": False,
        "blockers": blockers,
        "continuity": continuity,
        "fact_review": fact_review,
        "finding_gate": finding_report,
        "note": "Read-only preflight. It neither executes audit actions nor authorizes or submits findings.",
    }
    print(f"Workflow preflight: {slug} — {disposition}")
    for blocker in blockers:
        print(f"  - {blocker}")
    if disposition == "FINDING_AUDIT_REQUIRED":
        print("  - Provide --finding to run the six readiness gates.")
    if args.output:
        output_path = Path(args.output).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"JSON report: {output_path}")
    return 1 if disposition == "HOLD" else 0


def cmd_continuity_audit(args: argparse.Namespace) -> int:
    """Audit active-bounty identity, continuity, memory provenance, and state integrity."""
    bounty_root = resolve_bounty_root()
    slug = get_active_bounty_slug()
    state_file = bounty_root / "state.md"
    scope_file = bounty_root / "scope.md"
    snapshot_file = bounty_root / "snapshots" / "scope.sha256"
    facts_file = bounty_root / "facts.md"
    ledger_file = bounty_root / "logs" / "hypotheses.jsonl"

    state_text = state_file.read_text(encoding="utf-8", errors="replace") if state_file.is_file() else ""
    state_match = re.search(r"^# State:\s*(\S+)\s*$", state_text, re.MULTILINE)
    identity_issues = []
    if not slug:
        identity_issues.append("MEMORY.md has no active bounty")
    if slug and slug != bounty_root.name:
        identity_issues.append(f"active bounty '{slug}' does not match directory '{bounty_root.name}'")
    if not state_match or state_match.group(1) != bounty_root.name:
        identity_issues.append("state.md heading does not match the active bounty directory")
    agent_registry = Path("global") / "agents"
    agent_names = []
    if agent_registry.is_dir():
        for agent_file in agent_registry.glob("*.md"):
            if agent_file.name in {"AGENT_SET.md", "CONTRACT.md"}:
                continue
            content = agent_file.read_text(encoding="utf-8", errors="replace")
            name_match = re.search(r"^name:\s*[\"']?([^\"'\r\n]+)", content, re.MULTILINE)
            if name_match:
                agent_names.append((name_match.group(1).strip(), agent_file.name))
    duplicate_agent_names = sorted(
        name for name in {item[0] for item in agent_names}
        if sum(1 for registered, _ in agent_names if registered == name) > 1
    )
    identity_issues.extend(f"duplicate agent identity '{name}'" for name in duplicate_agent_names)

    scope_status = "missing"
    scope_digest = None
    if scope_file.is_file() and snapshot_file.is_file():
        try:
            expected = snapshot_file.read_text(encoding="utf-8").strip().split()[0].lower()
            _, scope_digest = extract_normalized_scope(scope_file)
            scope_status = "locked" if expected == scope_digest.lower() else "mismatch"
        except (OSError, ValueError, IndexError):
            scope_status = "invalid"

    repo_heads = []
    for child in sorted(bounty_root.iterdir()):
        if child.is_dir() and (child / ".git").exists():
            try:
                result = subprocess.run(
                    ["git", "-C", str(child), "rev-parse", "HEAD"],
                    capture_output=True, text=True, check=False, timeout=5,
                )
                if result.returncode == 0:
                    repo_heads.append(result.stdout.strip().lower())
            except (OSError, subprocess.TimeoutExpired):
                pass

    scope_text = scope_file.read_text(encoding="utf-8", errors="replace") if scope_file.is_file() else ""
    pinned_commits = re.findall(r"\bcommit\s*[:` ]+([0-9a-fA-F]{7,40})", scope_text, re.I)
    unmatched_pins = [pin for pin in pinned_commits if not any(head.startswith(pin.lower()) for head in repo_heads)]

    fact_lines = facts_file.read_text(encoding="utf-8", errors="replace").splitlines() if facts_file.is_file() else []
    fact_records = [line for line in fact_lines if re.match(r"\s*-\s*FACT-\d+\b", line)]
    missing_provenance = [line for line in fact_records if not PROVENANCE_TAG_RE.search(line)]
    fact_commits = re.findall(r"\[SRC:[^\]]*@([0-9a-fA-F]{7,40})\]", "\n".join(fact_records))
    stale_fact_commits = []
    if pinned_commits:
        for commit in sorted(set(fact_commits), key=str.lower):
            if not any(commit.lower().startswith(pin.lower()) or pin.lower().startswith(commit.lower()) for pin in pinned_commits):
                stale_fact_commits.append(commit)
    marked_stale_facts = sum(1 for line in fact_records if re.search(r"\bSTALE\b", line, re.I))

    malformed_ledger_lines = []
    if ledger_file.is_file():
        for number, line in enumerate(ledger_file.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if line.strip():
                try:
                    if not isinstance(json.loads(line), dict):
                        malformed_ledger_lines.append(number)
                except json.JSONDecodeError:
                    malformed_ledger_lines.append(number)

    run_ledger_file = bounty_root / "logs" / "execution_ledger.jsonl"
    run_ledger_count, run_ledger_error = _verify_run_ledger(run_ledger_file, bounty_root)

    phase_present = bool(re.search(r"^Phase:\s*.+$", state_text, re.MULTILINE))
    report = {
        "bounty": bounty_root.name,
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "identity": {"status": "attention" if identity_issues else "ok", "issues": identity_issues},
        "continuity": {
            "status": "attention" if not state_text or not phase_present or unmatched_pins else "ok",
            "state_present": state_file.is_file(),
            "phase_present": phase_present,
            "repositories_found": len(repo_heads),
            "unmatched_scope_commits": unmatched_pins,
        },
        "memory": {
            "status": "attention" if not facts_file.is_file() or missing_provenance or stale_fact_commits else "ok",
            "fact_records": len(fact_records),
            "missing_provenance_count": len(missing_provenance),
            "fact_commits_outside_scope_pins": stale_fact_commits,
            "facts_marked_stale": marked_stale_facts,
        },
        "stability": {
            "status": "blocked" if scope_status in {"missing", "mismatch", "invalid"} else ("attention" if malformed_ledger_lines or run_ledger_error else "ok"),
            "scope_snapshot": scope_status,
            "scope_sha256": scope_digest,
            "malformed_hypothesis_lines": malformed_ledger_lines,
            "execution_ledger_entries": run_ledger_count,
            "execution_ledger_error": run_ledger_error,
        },
        "note": "Read-only consistency checks; a clean report is not proof of protocol security or finding validity.",
    }

    print(f"Continuity audit: {bounty_root.name}")
    for section in ("identity", "continuity", "memory", "stability"):
        print(f"[{report[section]['status'].upper()}] {section}")
    for issue in identity_issues:
        print(f"  - {issue}")
    for pin in unmatched_pins:
        print(f"  - Scope commit not present in local checkout: {pin}")
    for commit in stale_fact_commits:
        print(f"  - Fact commit is outside current scope pins: {commit}")
    if missing_provenance:
        print(f"  - Facts without provenance tags: {len(missing_provenance)}")
    if malformed_ledger_lines:
        print(f"  - Malformed hypothesis ledger lines: {malformed_ledger_lines}")
    if run_ledger_error:
        print(f"  - Execution ledger integrity error: {run_ledger_error}")

    output = getattr(args, "output", None)
    if output:
        output_path = Path(output).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"JSON report: {output_path}")
    return 1 if any(report[section]["status"] != "ok" for section in ("identity", "continuity", "memory", "stability")) else 0


def cmd_scope_lock(args: argparse.Namespace) -> int:
    bounty_root = resolve_bounty_root(None)
    scope_file = Path(args.scope_file) if args.scope_file else bounty_root / "scope.md"
    if args.snapshot_file:
        snap_file = Path(args.snapshot_file)
    elif args.scope_file:
        snap_file = scope_file.parent / "snapshots" / "scope.sha256"
    else:
        snap_file = bounty_root / "snapshots" / "scope.sha256"

    try:
        _, digest = extract_normalized_scope(scope_file)
    except Exception as e:
        print(f"[FAIL] Error reading scope: {e}")
        return 1

    snap_file.parent.mkdir(parents=True, exist_ok=True)
    snap_file.write_text(f"{digest}\n", encoding="utf-8")

    # If log output is desired
    if args.output:
        out_p = Path(args.output)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        rec = {
            "status": "OK",
            "action": "scope-lock",
            "scope_file": str(scope_file),
            "snapshot_file": str(snap_file),
            "sha256_lf": digest,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        out_p.write_text(json.dumps(rec, indent=2), encoding="utf-8")

    print("[OK] Scope locked successfully.")
    print(f"     Scope File:    {scope_file}")
    print(f"     SHA-256 (LF):  {digest}")
    print(f"     Snapshot File: {snap_file}")
    return 0

def cmd_scope_verify(args: argparse.Namespace) -> int:
    bounty_root = resolve_bounty_root(None)
    scope_file = Path(args.scope_file) if args.scope_file else bounty_root / "scope.md"
    if args.snapshot_file:
        snap_file = Path(args.snapshot_file)
    elif args.scope_file:
        snap_file = scope_file.parent / "snapshots" / "scope.sha256"
    else:
        snap_file = bounty_root / "snapshots" / "scope.sha256"

    if not scope_file.is_file():
        print(f"[FAIL] Scope file not found: {scope_file}")
        return 1
    if not snap_file.is_file():
        print(f"[FAIL] Snapshot file not found: {snap_file}")
        return 1

    try:
        expected = snap_file.read_text(encoding="utf-8").strip().split()[0].lower()
        _, actual = extract_normalized_scope(scope_file)
    except Exception as e:
        print(f"[FAIL] Error reading scope files: {e}")
        return 1

    if expected == actual.lower():
        print(f"[OK] Scope integrity verified: {actual}")
        return 0
    else:
        print("[FAIL] SCOPE MISMATCH DETECTED (Fail-closed!)")
        print(f"       Expected: {expected}")
        print(f"       Actual:   {actual}")
        print("Freeze all candidate findings until scope change is confirmed by the user.")
        return 1

def cmd_hyp_add(args: argparse.Namespace) -> int:
    ledger_file = resolve_ledger_file(args.ledger)
    ledger_file.parent.mkdir(parents=True, exist_ok=True)

    entry = {
        "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "type": "HYPOTHESIS_CREATED",
        "id": args.id,
        "target": args.target,
        "actor": args.actor,
        "prediction": args.prediction,
        "status": "pending",
        "evidence": None,
        "kill_category": None,
        "kill_reason": None,
    }
    with open(ledger_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")

    print(f"[OK] Hypothesis {args.id} recorded as 'pending' in {ledger_file}")
    return 0

def cmd_hyp_status(args: argparse.Namespace) -> int:
    ledger_file = resolve_ledger_file(args.ledger)
    if not ledger_file.is_file():
        print(f"[FAIL] Ledger not found: {ledger_file}")
        return 1

    status = args.status.lower()
    if status == "killed" and (not args.category or not args.reason):
        print("[FAIL] Kills require both --category and --reason (kills are valuable learning data).")
        return 1

    # Verify hypothesis exists in append-only log
    exists = False
    with open(ledger_file, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            e = json.loads(line)
            if e.get("id") == args.id:
                exists = True
                break

    if not exists:
        print(f"[FAIL] Hypothesis {args.id} not found in ledger. Add it with hyp-add first.")
        return 1

    # Strictly APPEND-ONLY adhering to GEMINI.md Part 5 Rule 5.3
    update_entry = {
        "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "type": "HYPOTHESIS_STATUS_UPDATE",
        "id": args.id,
        "status": status,
        "kill_category": args.category if status == "killed" else None,
        "kill_reason": args.reason if status == "killed" else None,
        "evidence": args.evidence,
    }
    with open(ledger_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(update_entry) + "\n")

    print(f"[OK] Hypothesis {args.id} status transition to '{status}' appended to {ledger_file.name}.")
    return 0

def cmd_hyp_list(args: argparse.Namespace) -> int:
    ledger_file = resolve_ledger_file(args.ledger)
    if not ledger_file.is_file():
        print(f"[INFO] No hypotheses found at {ledger_file}.")
        return 0

    hypotheses = {}
    with open(ledger_file, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            e = json.loads(line)
            hid = e.get("id")
            if not hid:
                continue
            if hid not in hypotheses:
                hypotheses[hid] = e
            else:
                hypotheses[hid].update(e)

    filter_status = (args.status or "").lower()
    print("===============================================================")
    print(f"[*] HYPOTHESIS LEDGER ({ledger_file.name})")
    print("---------------------------------------------------------------")
    count = 0
    for hid, data in hypotheses.items():
        st = data.get("status", "pending")
        if filter_status and st != filter_status:
            continue
        count += 1
        print(f"ID: {hid:8s} | Status: {st.upper():12s} | Target: {data.get('target', 'N/A')}")
        print(f"  Prediction: {data.get('prediction', 'N/A')}")
        if st == "killed":
            print(f"  Kill Cat:   {data.get('kill_category', 'N/A')}")
            print(f"  Kill Reason:{data.get('kill_reason', 'N/A')}")
        if data.get("evidence"):
            print(f"  Evidence:   {data.get('evidence')}")
        print("---------------------------------------------------------------")
    print(f"Total matching hypotheses: {count}")
    print("===============================================================")
    return 0

def cmd_kills(args: argparse.Namespace) -> int:
    ledger_file = resolve_ledger_file(args.ledger)
    if not ledger_file.is_file():
        print(f"[INFO] No hypotheses found at {ledger_file}.")
        return 0

    hypotheses = {}
    with open(ledger_file, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            e = json.loads(line)
            hid = e.get("id")
            if hid:
                if hid not in hypotheses:
                    hypotheses[hid] = e
                else:
                    hypotheses[hid].update(e)

    kill_cats = {}
    for h in hypotheses.values():
        if h.get("status") == "killed":
            cat = h.get("kill_category") or "unspecified"
            kill_cats[cat] = kill_cats.get(cat, 0) + 1

    print("===============================================================")
    print("[*] TOP PRE-POC KILL CATEGORIES (Filters to check first)")
    print("---------------------------------------------------------------")
    if not kill_cats:
        print("No killed hypotheses recorded yet.")
    else:
        for cat, cnt in sorted(kill_cats.items(), key=lambda x: x[1], reverse=True):
            print(f"  [{cnt}x] {cat}")
    print("===============================================================")
    return 0

def cmd_poc_audit(args: argparse.Namespace) -> int:
    poc_path = Path(args.poc_file)
    if not poc_path.is_file():
        print(f"[FAIL] PoC file not found: {poc_path}")
        return 1

    code = poc_path.read_text(encoding="utf-8", errors="ignore")
    code_stripped = strip_solidity_comments(code)
    issues = []
    passes = []

    # 1. Bare expectRevert check on stripped code (avoids false positives in comments)
    if BARE_EXPECT_REVERT.search(code_stripped):
        issues.append("Found bare 'vm.expectRevert();'. Must specify selector or error type (e.g. abi.encodeWithSelector(...) or stdError).")
    else:
        passes.append("No bare vm.expectRevert() calls found.")

    # 2. Specific expectRevert check on stripped code
    if SPECIFIC_EXPECT_REVERT.search(code_stripped):
        passes.append("Specific custom error revert expectation detected.")

    # 3. Fork block pinning check on stripped code
    if FORK_PIN_PATTERN.search(code_stripped):
        passes.append("Fork block or fork creation reference detected.")
    else:
        issues.append("No fork block pinning (createSelectFork / rollFork) detected in PoC. Pinned state required.")

    # 4. Unprivileged attacker check on stripped code
    if UNPRIVILEGED_ACTOR_PATTERN.search(code_stripped):
        passes.append("Explicit unprivileged actor or prank setup detected.")
    else:
        issues.append("No explicit unprivileged actor (makeAddr('attacker') or vm.prank) detected.")

    # 5. Delta / impact assertion check on stripped code
    if DELTA_ASSERT_PATTERN.search(code_stripped):
        passes.append("Explicit balance or state delta assertions detected.")
    else:
        issues.append("Missing explicit balance delta assertions (e.g. assertEq(balanceAfter - balanceBefore, delta)).")

    # 6. Test suite structure check (benign, exploit, boundary, post-patch)
    test_funcs = re.findall(r"function\s+(test[A-Za-z0-9_]*)\s*\(", code_stripped)
    has_benign = any("benign" in fn.lower() or "control" in fn.lower() for fn in test_funcs)
    has_exploit = any("exploit" in fn.lower() or "poc" in fn.lower() for fn in test_funcs)

    if len(test_funcs) >= 4 and has_benign and has_exploit:
        passes.append(f"Full 4-test suite detected ({len(test_funcs)} test functions including benign control and exploit).")
    elif len(test_funcs) >= 2:
        passes.append(f"Multiple test functions ({len(test_funcs)}) detected.")
        if not has_benign:
            issues.append("Consider adding a test_Benign() control test demonstrating standard behavior.")
    else:
        issues.append(f"Only {len(test_funcs)} test function(s) detected. Recommend: test_Benign(), test_Exploit(), test_Boundary(), test_PostPatch().")

    print("===============================================================")
    print(f"[*] FOUNDRY POC STRUCTURAL AUDIT: {poc_path.name}")
    print("---------------------------------------------------------------")
    for p in passes:
        print(f"  [PASS] {p}")
    for iss in issues:
        print(f"  [WARN] {iss}")
    print("---------------------------------------------------------------")
    failed = any("bare 'vm.expectrevert" in iss.lower() or "no fork block pinning" in iss.lower() for iss in issues)

    if getattr(args, "output", None):
        out_p = Path(args.output).resolve()
        out_p.parent.mkdir(parents=True, exist_ok=True)
        res = {
            "status": "FAIL" if failed else "OK",
            "action": "poc-audit",
            "poc_file": str(poc_path),
            "passes": passes,
            "issues": issues,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        out_p.write_text(json.dumps(res, indent=2), encoding="utf-8")

    if failed:
        print("Result: FAILED Critical Non-Negotiables (Remediate items above)")
        return 1
    else:
        print("Result: PASSED PoC Structural Quality Review")
        return 0


def cmd_gate_audit(args: argparse.Namespace) -> int:
    finding_path = Path(args.finding).resolve()
    if not finding_path.is_file():
        print(f"[FAIL] Finding file not found: {finding_path}")
        return 1

    bounty_root_arg = args.bounty_root
    if bounty_root_arg == "." or not bounty_root_arg:
        # Check if finding is inside bounties/<slug>/findings/
        parts = finding_path.parts
        if "findings" in parts:
            idx = parts.index("findings")
            if idx > 0:
                bounty_root = Path(*parts[:idx])
            else:
                bounty_root = resolve_bounty_root(None)
        else:
            bounty_root = resolve_bounty_root(None)
    else:
        bounty_root = resolve_bounty_root(bounty_root_arg)

    content = finding_path.read_text(encoding="utf-8", errors="ignore")
    lines = content.splitlines()

    gates = {
        "gate_1_source": {"pass": False, "detail": ""},
        "gate_2_reproduction": {"pass": False, "detail": ""},
        "gate_3_scope": {"pass": False, "detail": ""},
        "gate_4_duplicate": {"pass": False, "detail": ""},
        "gate_5_severity": {"pass": False, "detail": ""},
        "gate_6_provenance": {"pass": False, "detail": ""},
    }

    # Gate 1: Source Gate
    src_matches = SRC_TAG_RE.findall(content)
    if src_matches:
        gates["gate_1_source"]["pass"] = True
        gates["gate_1_source"]["detail"] = f"Found {len(src_matches)} valid [SRC: path:line @commit] tag(s)."
    else:
        gates["gate_1_source"]["pass"] = False
        gates["gate_1_source"]["detail"] = "No valid [SRC: path:line @commit] citations found."

    # Gate 2: Reproduction Gate
    poc_match = POC_TAG_RE.search(content)
    poc_ledger = bounty_root / "logs" / "poc_ledger.jsonl"
    if poc_match and poc_match.group(1).upper() == "PASS":
        if poc_ledger.is_file():
            try:
                rel_path = poc_ledger.relative_to(bounty_root)
            except ValueError:
                rel_path = poc_ledger
            gates["gate_2_reproduction"]["pass"] = True
            gates["gate_2_reproduction"]["detail"] = f"Cites [POC: PASS] and poc_ledger exists at {rel_path}."
        else:
            gates["gate_2_reproduction"]["pass"] = False
            gates["gate_2_reproduction"]["detail"] = "Cites [POC: PASS], but poc_ledger.jsonl is missing (dual-plane execution logs unverified)."
    else:
        gates["gate_2_reproduction"]["pass"] = False
        gates["gate_2_reproduction"]["detail"] = "No [POC: PASS] citation present in finding."

    # Gate 3: Scope Gate
    scope_path = bounty_root / "scope.md"
    affected_match = re.search(r"-\s*\*\*Affected:\*\*\s*([^\r\n]+)", content, re.I)
    if scope_path.is_file() and affected_match:
        scope_text = scope_path.read_text(encoding="utf-8", errors="ignore").lower()
        affected_str = affected_match.group(1)
        # Clean out tags before token extraction
        affected_str_clean = re.sub(r"\[[A-Z]+:[^\]]+\]", "", affected_str)
        raw_tokens = [t.strip(" `[],;()") for t in re.split(r"[\s,`\[\];()]+", affected_str_clean)]
        stop_words = {"at", "in", "the", "and", "or", "of", "to", "on", "for", "with", "from", "contract", "address", "line", "chain"}
        tokens = []
        for t in raw_tokens:
            if not t or t.lower() in stop_words or len(t) < 2:
                continue
            tokens.append(t)
            parts = re.split(r"[\.:]+", t)
            for p in parts:
                if p and p.lower() not in stop_words and len(p) >= 2:
                    tokens.append(p)
        in_scope = any(token.lower() in scope_text for token in tokens)
        if in_scope:
            gates["gate_3_scope"]["pass"] = True
            gates["gate_3_scope"]["detail"] = f"Affected target validated against {scope_path.name}."
        else:
            gates["gate_3_scope"]["pass"] = False
            gates["gate_3_scope"]["detail"] = f"Affected target '{affected_str}' not found in {scope_path.name}."
    else:
        gates["gate_3_scope"]["pass"] = False
        gates["gate_3_scope"]["detail"] = "Missing scope.md or Affected target header."

    # Gate 4: Duplicate Gate
    known_ledger = bounty_root / "logs" / "known_issues.jsonl"
    has_known_check = bool(re.search(r"(?:duplicate|known\s*issue)[^*:\r\n]*[*:\s]+(?:checked|verified|none|pass|clean|no\s*duplicates?|not\s*found|n/a|0\b)", content, re.I))
    if known_ledger.is_file() or has_known_check:
        gates["gate_4_duplicate"]["pass"] = True
        gates["gate_4_duplicate"]["detail"] = "Known issues / duplicate registry check recorded."
    else:
        gates["gate_4_duplicate"]["pass"] = False
        gates["gate_4_duplicate"]["detail"] = "No duplicate check or known_issues.jsonl review record verified."

    # Gate 5: Severity Gate
    sev_match = re.search(r"-\s*\*\*Severity[^:]*:\*\*\s*([^\r\n]+)", content, re.I)
    if sev_match and any(lvl.lower() in sev_match.group(1).lower() for lvl in ["critical", "high", "medium", "low", "informational"]):
        gates["gate_5_severity"]["pass"] = True
        gates["gate_5_severity"]["detail"] = f"Severity defined using valid program level: {sev_match.group(1).strip()}."
    else:
        gates["gate_5_severity"]["pass"] = False
        gates["gate_5_severity"]["detail"] = "Missing or invalid 'Severity (program scale):' header."

    # Gate 6: Provenance Tag Audit on Substantive Claim Lines
    in_substantive = False
    in_code_block = False
    substantive_count = 0
    untagged_lines = []
    for line_no, line in enumerate(lines, start=1):
        stripped = line.strip()
        # Check for substantive section headers (Summary, Root Cause, Impact)
        if re.match(r"^#{1,4}\s+(summary|root\s*cause|impact)\b", stripped, re.I):
            in_substantive = True
            in_code_block = False
            substantive_count += 1
            continue
        elif stripped.startswith("#"):
            in_substantive = False
            in_code_block = False

        if in_substantive and stripped:
            if stripped.startswith("```"):
                in_code_block = not in_code_block
                continue
            if in_code_block:
                continue
            if META_BULLET_RE.match(stripped):
                continue
            if not PROVENANCE_TAG_RE.search(stripped):
                untagged_lines.append((line_no, stripped))

    if untagged_lines:
        gates["gate_6_provenance"]["pass"] = False
        gates["gate_6_provenance"]["detail"] = f"Found {len(untagged_lines)} untagged claim line(s), e.g. line {untagged_lines[0][0]}."
    elif substantive_count == 0:
        # Check inline summary/root cause/impact
        if re.search(r"-\s*\*\*Summary:\*\*.*\[(SRC|LOCAL|POC|TOOL|WEB|USER|ASSUMPTION|UNKNOWN)", content, re.I) and \
           re.search(r"-\s*\*\*Root\s*cause:\*\*.*\[(SRC|LOCAL|POC|TOOL|WEB|USER|ASSUMPTION|UNKNOWN)", content, re.I) and \
           re.search(r"-\s*\*\*Impact:\*\*.*\[(SRC|LOCAL|POC|TOOL|WEB|USER|ASSUMPTION|UNKNOWN)", content, re.I):
            gates["gate_6_provenance"]["pass"] = True
            gates["gate_6_provenance"]["detail"] = "Audited inline Summary, Root cause, and Impact tagged claims."
        else:
            gates["gate_6_provenance"]["pass"] = False
            gates["gate_6_provenance"]["detail"] = "Missing tagged Summary, Root cause, or Impact claims."
    else:
        gates["gate_6_provenance"]["pass"] = True
        gates["gate_6_provenance"]["detail"] = f"All claim lines in {substantive_count} substantive sections verified tagged."

    passed_count = sum(1 for g in gates.values() if g["pass"])
    pass_rate = f"{passed_count}/6"
    failed_gates = [name for name, result in gates.items() if not result["pass"]]
    disposition = "HUMAN_REVIEW_REQUIRED" if passed_count == 6 else "HOLD"

    print("===============================================================")
    print(f"[*] READINESS GATE AUDIT (6 GATES): {finding_path.name}")
    print(f"    Bounty Context: {bounty_root.name}")
    print("---------------------------------------------------------------")
    for gname, info in gates.items():
        symbol = "PASS" if info["pass"] else "FAIL"
        print(f"  [{symbol:4s}] {gname:20s}: {info['detail']}")
    print("---------------------------------------------------------------")
    print(f"Score: {pass_rate} Gates Passed ({(passed_count/6.0)*100:.1f}%)")

    if getattr(args, "output", None):
        out_p = Path(args.output).resolve()
        out_p.parent.mkdir(parents=True, exist_ok=True)
        res = {
            "status": "OK" if passed_count == 6 else "FAIL",
            "action": "gate-audit",
            "disposition": disposition,
            "authorization_granted": False,
            "failed_gates": failed_gates,
            "next_action": "Obtain explicit human review; this audit never authorizes submission." if passed_count == 6 else "Resolve failed gates and rerun the audit.",
            "finding_file": str(finding_path),
            "passed_count": passed_count,
            "pass_rate": pass_rate,
            "gates": gates,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        out_p.write_text(json.dumps(res, indent=2), encoding="utf-8")

    if passed_count == 6:
        print("Disposition: HUMAN REVIEW REQUIRED (submission is not authorized)")
        print("Automated checks do not establish finding validity or grant approval.")
        return 0
    else:
        print(f"Disposition: HOLD ({6 - passed_count} gate(s) failing)")
        return 1


def cmd_learn_summary(args: argparse.Namespace) -> int:
    ledger_file = resolve_ledger_file(args.ledger)
    if not ledger_file.is_file():
        print(f"[INFO] No hypothesis ledger found at {ledger_file}.")
        return 0

    hypotheses = {}
    with open(ledger_file, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            e = json.loads(line)
            hid = e.get("id")
            if hid:
                if hid not in hypotheses:
                    hypotheses[hid] = e
                else:
                    hypotheses[hid].update(e)

    total = len(hypotheses)
    status_counts = {}
    kill_categories = {}

    for e in hypotheses.values():
        st = e.get("status", "pending")
        status_counts[st] = status_counts.get(st, 0) + 1
        cat = e.get("kill_category")
        if cat:
            kill_categories[cat] = kill_categories.get(cat, 0) + 1

    print("===============================================================")
    print("[*] CONTINUOUS LEARNING & RETROSPECTIVE SUMMARY")
    print(f"    Ledger: {ledger_file}")
    print("---------------------------------------------------------------")
    print(f"Total Unique Hypotheses Tracked: {total}")
    for st, count in status_counts.items():
        print(f"  * {st.capitalize():12s}: {count}")
    if kill_categories:
        print("\nTop Pre-PoC Kill Filters:")
        sorted_kills = sorted(kill_categories.items(), key=lambda x: x[1], reverse=True)
        for cat, count in sorted_kills:
            print(f"  - [{count}x] {cat}")
    print("===============================================================")
    return 0

def cmd_lesson_add(args: argparse.Namespace) -> int:
    lessons_file = resolve_lessons_file(args.file)
    lessons_file.parent.mkdir(parents=True, exist_ok=True)

    date_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    tags_str = f"[{args.tags}]" if args.tags else ""
    line = f"- **{args.id}** ({date_str}) {tags_str}: {args.text}\n"

    with open(lessons_file, "a", encoding="utf-8") as f:
        f.write(line)

    print(f"[OK] Lesson {args.id} appended to {lessons_file.name}")
    return 0

def cmd_lesson_list(args: argparse.Namespace) -> int:
    lessons_file = resolve_lessons_file(args.file)
    if not lessons_file.is_file():
        print(f"[INFO] No lessons file found at {lessons_file}.")
        return 0

    print("===============================================================")
    print(f"[*] AUDIT RETROSPECTIVE LESSONS ({lessons_file.name})")
    print("---------------------------------------------------------------")
    content = lessons_file.read_text(encoding="utf-8", errors="ignore")
    print(content.strip() or "No lessons recorded yet.")
    print("===============================================================")
    return 0

def cmd_outcome_add(args: argparse.Namespace) -> int:
    bounty_root = resolve_bounty_root(None)
    outcomes_file = bounty_root / "logs" / "triage_outcomes.jsonl"
    outcomes_file.parent.mkdir(parents=True, exist_ok=True)

    entry = {
        "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "id": args.id,
        "predicted": args.predicted,
        "actual": args.actual,
        "notes": args.notes,
    }
    with open(outcomes_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")

    print(f"[OK] Outcome for {args.id} recorded in {outcomes_file.name}")
    return 0

def cmd_calibrate(args: argparse.Namespace) -> int:
    if getattr(args, "file", None):
        outcomes_file = Path(args.file).resolve()
    else:
        bounty_root = resolve_bounty_root(getattr(args, "bounty_root", None))
        outcomes_file = bounty_root / "logs" / "triage_outcomes.jsonl"

    if not outcomes_file.is_file():
        print(f"[INFO] No triage outcomes found at {outcomes_file}. Log outcomes with outcome-add!")
        return 0

    total = 0
    overestimated = 0
    underestimated = 0
    matched = 0
    sev_rank = {
        "critical": 4,
        "high": 3,
        "medium": 2,
        "low": 1,
        "informational": 0,
        "invalid": -1,
        "duplicate": -1,
        "rejected": -1,
        "out of scope": -1,
        "abandoned": -1,
        "spam": -1,
    }

    with open(outcomes_file, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            e = json.loads(line)
            total += 1
            pred_r = sev_rank.get(e.get("predicted", "").lower(), 0)
            act_r = sev_rank.get(e.get("actual", "").lower(), 0)
            if pred_r > act_r:
                overestimated += 1
            elif pred_r < act_r:
                underestimated += 1
            else:
                matched += 1

    if total == 0:
        print("[INFO] No triage outcome entries found.")
        return 0

    if getattr(args, "output", None):
        out_p = Path(args.output).resolve()
        out_p.parent.mkdir(parents=True, exist_ok=True)
        res = {
            "status": "OK",
            "action": "calibrate",
            "outcomes_file": str(outcomes_file),
            "total": total,
            "matched": matched,
            "overestimated": overestimated,
            "underestimated": underestimated,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        out_p.write_text(json.dumps(res, indent=2), encoding="utf-8")

    print("===============================================================")
    print("[*] SEVERITY CALIBRATION REPORT")
    print(f"Total Outcomes Evaluated: {total}")
    print(f"  * Matched:       {matched} ({(matched/total)*100:.1f}%)")
    print(f"  * Overestimated: {overestimated} ({(overestimated/total)*100:.1f}%)")
    print(f"  * Underestimated:{underestimated} ({(underestimated/total)*100:.1f}%)")
    print("---------------------------------------------------------------")
    if overestimated > underestimated:
        print("[!] BIAS DETECTED: Tendency to OVERESTIMATE severity.")
        print("    Recommendation: Discount speculative impact, verify fee/gas bounds before claiming High.")
    elif underestimated > overestimated:
        print("[!] BIAS DETECTED: Tendency to UNDERESTIMATE severity.")
        print("    Recommendation: Check systemic cascading liquidation and unlock callback impacts.")
    else:
        print("[OK] Severity ratings are well-calibrated.")
    print("===============================================================")
    return 0

def cmd_fact_record(args: argparse.Namespace) -> int:
    bounty_root = resolve_bounty_root(getattr(args, "bounty_root", None))
    facts_file = Path(args.facts_file).resolve() if getattr(args, "facts_file", None) else bounty_root / "facts.md"
    fact_text = args.fact.strip()
    tag = args.tag.strip()
    status = args.status.strip() if getattr(args, "status", None) else "CURRENT"
    date_str = datetime.date.today().isoformat()

    if not PROVENANCE_TAG_RE.search(tag):
        print(
            f"[FAIL] Invalid provenance tag '{tag}'. Must match [TYPE: ...] format.",
            file=sys.stderr,
        )
        return 1

    facts_file.parent.mkdir(parents=True, exist_ok=True)
    existing_content = facts_file.read_text(encoding="utf-8") if facts_file.exists() else ""

    existing_ids = [int(m) for m in re.findall(r"FACT-(\d+)", existing_content)]
    next_id = max(existing_ids, default=0) + 1
    fact_id_str = f"FACT-{next_id:03d}"

    new_line = f"- {fact_id_str}: {fact_text} {tag} Status: {status}, captured {date_str}.\n"

    with open(facts_file, "a", encoding="utf-8") as f:
        f.write(new_line)

    if getattr(args, "output", None):
        out_p = Path(args.output).resolve()
        out_p.parent.mkdir(parents=True, exist_ok=True)
        res = {
            "status": "OK",
            "action": "fact-record",
            "fact_id": fact_id_str,
            "fact_line": new_line.strip(),
            "facts_file": str(facts_file),
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        out_p.write_text(json.dumps(res, indent=2), encoding="utf-8")

    print(f"[OK] Recorded {fact_id_str} in {facts_file}")
    return 0


def cmd_fact_review(args: argparse.Namespace) -> int:
    """Review fact memory for stale, unproven, out-of-pin, and duplicate entries."""
    bounty_root = resolve_bounty_root(args.bounty_root)
    facts_file = bounty_root / "facts.md"
    scope_file = bounty_root / "scope.md"
    if not facts_file.is_file():
        print(f"[FAIL] Facts file not found: {facts_file}", file=sys.stderr)
        return 1
    text = facts_file.read_text(encoding="utf-8", errors="replace")
    scope_text = scope_file.read_text(encoding="utf-8", errors="replace") if scope_file.is_file() else ""
    pins = re.findall(r"\bcommit\s*[:` ]+([0-9a-fA-F]{7,40})", scope_text, re.I)
    records = []
    for match in re.finditer(r"(?ms)^-\s*(FACT-\d+):\s*(.*?)(?=^-\s*FACT-\d+:|\Z)", text):
        fact_id, body = match.group(1), match.group(2).strip()
        tags = PROVENANCE_TAG_RE.findall(body)
        status_match = re.search(r"\bStatus:\s*([A-Za-z_-]+)", body, re.I)
        status = status_match.group(1).upper() if status_match else "UNSPECIFIED"
        claim = re.sub(r"\bStatus:\s*[^.\r\n]+(?:\.\s*)?", " ", body, flags=re.I)
        claim = PROVENANCE_TAG_RE.sub(" ", claim)
        normalized = re.sub(r"[^a-z0-9]+", "", claim.lower())
        commits = SRC_TAG_RE.findall(body)
        out_of_scope = [commit for _, _, commit in commits if pins and not any(
            commit.lower().startswith(pin.lower()) or pin.lower().startswith(commit.lower()) for pin in pins
        )]
        records.append({
            "id": fact_id,
            "status": status,
            "has_provenance": bool(tags),
            "stale_status": status in {"STALE", "DEPRECATED", "SUPERSEDED", "RETRACTED"},
            "out_of_scope_commits": sorted(set(out_of_scope)),
            "normalized_claim": normalized,
        })

    duplicate_groups = {}
    for record in records:
        key = record["normalized_claim"]
        if key:
            duplicate_groups.setdefault(key, []).append(record["id"])
    duplicates = [ids for ids in duplicate_groups.values() if len(ids) > 1]
    missing_provenance = [record["id"] for record in records if not record["has_provenance"]]
    stale_facts = [record["id"] for record in records if record["stale_status"]]
    out_of_scope = {record["id"]: record["out_of_scope_commits"] for record in records if record["out_of_scope_commits"]}
    report = {
        "bounty": bounty_root.name,
        "facts_file": str(facts_file),
        "fact_count": len(records),
        "scope_pins_found": len(pins),
        "missing_provenance": missing_provenance,
        "explicitly_stale": stale_facts,
        "commits_outside_scope_pins": out_of_scope,
        "possible_exact_duplicates": duplicates,
        "note": "Read-only review. Duplicate detection is textual; no facts were merged or deleted.",
    }
    print(f"Fact review: {bounty_root.name} ({len(records)} records)")
    findings = 0
    for label, values in (("Missing provenance", missing_provenance), ("Marked stale", stale_facts)):
        print(f"{label}: {len(values)}")
        findings += len(values)
    print(f"Facts citing commits outside scope pins: {len(out_of_scope)}")
    print(f"Possible exact duplicate groups: {len(duplicates)}")
    findings += len(out_of_scope) + len(duplicates)
    if args.output:
        output_path = Path(args.output).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"JSON report: {output_path}")
    print("No facts were changed or removed.")
    return 1 if findings else 0

def cmd_envelope_check(args: argparse.Namespace) -> int:
    envelope_file = Path(args.envelope).resolve()
    if not envelope_file.is_file():
        print(f"[FAIL] Envelope file not found: {envelope_file}", file=sys.stderr)
        return 1

    try:
        raw_text = envelope_file.read_text(encoding="utf-8")
        data = json.loads(raw_text)
    except Exception as e:
        print(f"[FAIL] Envelope is not valid JSON: {e}", file=sys.stderr)
        return 1

    errors = []
    # 0. Secret check adhering to GEMINI.md Part 2 Rule 7
    for pattern in SECRET_PATTERNS:
        if pattern.search(raw_text):
            errors.append("SECRET_EXPOSED: secret-like RPC key or private key pattern found in envelope payload")
            break

    # 1. Required top-level fields
    for field in REQUIRED_ENVELOPE_FIELDS:
        if field not in data:
            errors.append(f"Missing required field: '{field}'")

    # 2. Status validation
    status = data.get("status")
    if status is not None and status not in VALID_ENVELOPE_STATUSES:
        errors.append(f"Invalid status '{status}'. Valid: {sorted(VALID_ENVELOPE_STATUSES)}")

    # 3. Evidence list validation
    evidence_list = data.get("evidence", [])
    if not isinstance(evidence_list, list):
        errors.append("'evidence' must be a list")
    else:
        for idx, item in enumerate(evidence_list):
            if not isinstance(item, dict):
                errors.append(f"evidence[{idx}] must be an object")
                continue
            etype = item.get("type")
            if etype not in VALID_EVIDENCE_TYPES:
                errors.append(f"evidence[{idx}] unknown type: '{etype}'. Valid: {sorted(VALID_EVIDENCE_TYPES)}")
            if etype == "SRC":
                if not (isinstance(item.get("path"), str) and SRC_PATH_RE.match(item["path"])):
                    errors.append(f"evidence[{idx}] SRC path must be 'path:line'")
                if not (isinstance(item.get("commit"), str) and HEX40_RE.match(item["commit"])):
                    errors.append(f"evidence[{idx}] SRC commit must be 40-hex commit")
            elif etype in ("TOOL", "POC"):
                if not (isinstance(item.get("sha256"), str) and HEX64_RE.match(item["sha256"])):
                    errors.append(f"evidence[{idx}] {etype} needs a 64-hex sha256")

    is_valid = len(errors) == 0
    if getattr(args, "output", None):
        out_p = Path(args.output).resolve()
        out_p.parent.mkdir(parents=True, exist_ok=True)
        res = {
            "status": "OK" if is_valid else "INVALID",
            "action": "envelope-check",
            "envelope_file": str(envelope_file),
            "valid": is_valid,
            "errors": errors,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        out_p.write_text(json.dumps(res, indent=2), encoding="utf-8")

    if is_valid:
        print("[OK] Envelope validation PASSED.")
        return 0
    else:
        print(f"[FAIL] Envelope validation FAILED with {len(errors)} error(s):", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1


# --- Main Entry Point ---

def main() -> int:
    parser = argparse.ArgumentParser(description="Unified Smart Contract Bug Bounty Orchestration CLI")
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    # execution-matrix
    p_matrix = subparsers.add_parser("execution-matrix", help="Summarize bounty workflow artifacts and local repositories")
    p_matrix.add_argument("--bounty-root", default=None, help="Bounty directory (defaults to the active bounty)")
    p_matrix.add_argument("--output", default=None, help="Optional JSON report path")

    # Evidence integrity
    p_seal = subparsers.add_parser("evidence-seal", help="Create a SHA-256 Merkle manifest for bounty evidence")
    p_seal.add_argument("--bounty-root", default=None, help="Bounty directory (defaults to the active bounty)")
    p_seal.add_argument("--output", required=True, help="Path for the evidence manifest JSON")
    p_verify = subparsers.add_parser("evidence-verify", help="Verify evidence files against a Merkle manifest")
    p_verify.add_argument("--bounty-root", default=None, help="Bounty directory (defaults to the active bounty)")
    p_verify.add_argument("--manifest", required=True, help="Evidence manifest JSON to verify")

    # continuity-audit
    p_continuity = subparsers.add_parser("continuity-audit", help="Check active bounty identity, provenance, and state integrity")
    p_continuity.add_argument("--output", default=None, help="Optional JSON report path")

    # Manual, hash-chained execution evidence
    p_run_record = subparsers.add_parser("run-record", help="Record a stage result and optional artifact digest")
    p_run_record.add_argument("--stage", required=True, help="Short stage label; do not include secrets")
    p_run_record.add_argument("--status", choices=sorted(VALID_ENVELOPE_STATUSES), required=True)
    p_run_record.add_argument("--artifact", default=None, help="Existing file path relative to the active bounty")
    subparsers.add_parser("run-verify", help="Verify execution ledger chain and recorded artifact digests")
    p_run_observe = subparsers.add_parser("run-observe", help="Summarize recent ledger outcomes; read-only")
    p_run_observe.add_argument("--window", type=int, default=10, help="Recent records to summarize (1-1000)")
    p_telemetry = subparsers.add_parser("telemetry-report", help="Create a privacy-minimized local workflow metrics report")
    p_telemetry.add_argument("--output", default=None, help="Optional JSON report path")
    p_preflight = subparsers.add_parser("workflow-preflight", help="Combine read-only bounty controls into one disposition")
    p_preflight.add_argument("--finding", default=None, help="Optional finding file for the six readiness gates")
    p_preflight.add_argument("--output", default=None, help="Optional JSON report path")

    # route
    p_route = subparsers.add_parser("route", help="Route audit targets to appropriate sub-skills")
    p_route.add_argument("--target", "-t", required=True, help="File path, directory, keyword, or contract text")

    # scope-lock
    p_lock = subparsers.add_parser("scope-lock", help="Lock scope with SHA-256 snapshot")
    p_lock.add_argument("--scope-file", default=None)
    p_lock.add_argument("--snapshot-file", default=None)
    p_lock.add_argument("--output", default=None)

    # scope-verify
    p_ver = subparsers.add_parser("scope-verify", help="Verify scope against snapshot")
    p_ver.add_argument("--scope-file", default=None)
    p_ver.add_argument("--snapshot-file", default=None)

    # hyp-add
    p_hadd = subparsers.add_parser("hyp-add", help="Add hypothesis (append-only)")
    p_hadd.add_argument("--id", required=True)
    p_hadd.add_argument("--target", required=True)
    p_hadd.add_argument("--actor", default="unprivileged")
    p_hadd.add_argument("--prediction", required=True)
    p_hadd.add_argument("--ledger", default=None)

    # hyp-status / hyp-set
    for cmd_name in ["hyp-status", "hyp-set"]:
        p_hstat = subparsers.add_parser(cmd_name, help="Update hypothesis status (strictly append-only)")
        p_hstat.add_argument("--id", required=True)
        p_hstat.add_argument("--status", choices=["pending", "proved", "killed", "inconclusive"], required=True)
        p_hstat.add_argument("--category", default=None)
        p_hstat.add_argument("--reason", default=None)
        p_hstat.add_argument("--evidence", default=None)
        p_hstat.add_argument("--ledger", default=None)

    # hyp-list
    p_hlist = subparsers.add_parser("hyp-list", help="List hypotheses from append-only stream")
    p_hlist.add_argument("--status", choices=["pending", "proved", "killed", "inconclusive"], default=None)
    p_hlist.add_argument("--ledger", default=None)

    # kills
    p_kills = subparsers.add_parser("kills", help="Display top kill categories to use as pre-PoC filters")
    p_kills.add_argument("--ledger", default=None)

    # poc-audit
    p_poc = subparsers.add_parser("poc-audit", help="Audit Foundry PoC structure (8 non-negotiables)")
    p_poc.add_argument("--poc-file", required=True)
    p_poc.add_argument("--output", default=None)

    # gate-audit / gate-check
    for cmd_name in ["gate-audit", "gate-check"]:
        p_gate = subparsers.add_parser(cmd_name, help="Run 6 readiness gates on candidate finding")
        p_gate.add_argument("--finding", required=True)
        p_gate.add_argument("--bounty-root", default=".")
        p_gate.add_argument("--output", default=None)

    # learn-summary
    p_learn = subparsers.add_parser("learn-summary", help="Analyze retrospective learning and kill patterns")
    p_learn.add_argument("--ledger", default=None)

    # lesson-add
    p_ladd = subparsers.add_parser("lesson-add", help="Append a new retrospective lesson")
    p_ladd.add_argument("--id", required=True)
    p_ladd.add_argument("--text", required=True)
    p_ladd.add_argument("--tags", default=None)
    p_ladd.add_argument("--file", default=None)

    # lesson-list
    p_llist = subparsers.add_parser("lesson-list", help="List retrospective lessons")
    p_llist.add_argument("--file", default=None)

    # outcome-add
    p_oadd = subparsers.add_parser("outcome-add", help="Record predicted vs actual outcome for severity calibration")
    p_oadd.add_argument("--id", required=True)
    p_oadd.add_argument("--predicted", required=True)
    p_oadd.add_argument("--actual", required=True)
    p_oadd.add_argument("--notes", default="")

    # calibrate
    p_cal = subparsers.add_parser("calibrate", help="Calculate severity calibration bias")
    p_cal.add_argument("--file", default=None)
    p_cal.add_argument("--bounty-root", default=None)
    p_cal.add_argument("--output", default=None)

    # fact-record
    p_frec = subparsers.add_parser("fact-record", help="Append provenance-tagged fact to facts.md")
    p_frec.add_argument("--fact", required=True)
    p_frec.add_argument("--tag", required=True)
    p_frec.add_argument("--status", default="CURRENT")
    p_frec.add_argument("--facts-file", default=None)
    p_frec.add_argument("--bounty-root", default=None)
    p_frec.add_argument("--output", default=None)

    # Read-only memory review; never forgets or consolidates records automatically
    p_freview = subparsers.add_parser("fact-review", help="Review fact memory for stale, duplicate, or weakly sourced entries")
    p_freview.add_argument("--bounty-root", default=None)
    p_freview.add_argument("--output", default=None)

    # envelope-check
    p_env = subparsers.add_parser("envelope-check", help="Validate agent envelope against standard schema")
    p_env.add_argument("--envelope", required=True)
    p_env.add_argument("--contract-file", default=None)
    p_env.add_argument("--output", default=None)

    args = parser.parse_args()
    if args.subcommand == "run-observe" and not 1 <= args.window <= 1000:
        parser.error("--window must be between 1 and 1000")
    if args.subcommand == "execution-matrix":
        return cmd_execution_matrix(args)
    elif args.subcommand == "evidence-seal":
        return cmd_evidence_seal(args)
    elif args.subcommand == "evidence-verify":
        return cmd_evidence_verify(args)
    elif args.subcommand == "continuity-audit":
        return cmd_continuity_audit(args)
    elif args.subcommand == "run-record":
        return cmd_run_record(args)
    elif args.subcommand == "run-verify":
        return cmd_run_verify(args)
    elif args.subcommand == "run-observe":
        return cmd_run_observe(args)
    elif args.subcommand == "telemetry-report":
        return cmd_telemetry_report(args)
    elif args.subcommand == "workflow-preflight":
        return cmd_workflow_preflight(args)
    elif args.subcommand == "route":
        return cmd_route(args)
    elif args.subcommand == "scope-lock":
        return cmd_scope_lock(args)
    elif args.subcommand == "scope-verify":
        return cmd_scope_verify(args)
    elif args.subcommand == "hyp-add":
        return cmd_hyp_add(args)
    elif args.subcommand in ("hyp-status", "hyp-set"):
        return cmd_hyp_status(args)
    elif args.subcommand == "hyp-list":
        return cmd_hyp_list(args)
    elif args.subcommand == "kills":
        return cmd_kills(args)
    elif args.subcommand == "poc-audit":
        return cmd_poc_audit(args)
    elif args.subcommand in ("gate-audit", "gate-check"):
        return cmd_gate_audit(args)
    elif args.subcommand == "learn-summary":
        return cmd_learn_summary(args)
    elif args.subcommand == "lesson-add":
        return cmd_lesson_add(args)
    elif args.subcommand == "lesson-list":
        return cmd_lesson_list(args)
    elif args.subcommand == "outcome-add":
        return cmd_outcome_add(args)
    elif args.subcommand == "calibrate":
        return cmd_calibrate(args)
    elif args.subcommand == "fact-record":
        return cmd_fact_record(args)
    elif args.subcommand == "fact-review":
        return cmd_fact_review(args)
    elif args.subcommand == "envelope-check":
        return cmd_envelope_check(args)
    return 0

if __name__ == "__main__":
    sys.exit(main())
