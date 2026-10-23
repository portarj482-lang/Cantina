#!/usr/bin/env python3
"""Core Hallucination & Citation Verification Engine for Pack E Triage Workflows.

Audits code citations in bounty reports against a pinned Git commit revision.
Produces:
  - hallucination_audit.json
  - hallucination_audit.provenance.json
"""

import argparse
import datetime
import glob
import importlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

SLUG_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,99}$")
COMMIT_REF_PATTERN = re.compile(r"^[A-Za-z0-9_./@~^-]+$")
MAX_BLOB_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB maximum blob limit
MAX_TOTAL_CITATIONS = 50000


def log_event(
    level: str,
    event: str,
    message: str,
    component: str = "hallucination_dropper",
    slug: Optional[str] = None,
    pinned_commit: Optional[str] = None,
    source: Optional[str] = None,
    processed_count: int = 0,
    error_code: Optional[str] = None,
) -> None:
    """Emit a structured JSON Lines event record to stderr."""
    payload = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "level": level,
        "event": event,
        "component": component,
        "slug": slug,
        "pinned_commit": pinned_commit,
        "source": source,
        "processed_count": processed_count,
        "error_code": error_code,
        "message": message,
    }
    sys.stderr.write(json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stderr.flush()


def find_repo_root(start_dir: Optional[Path] = None) -> Path:
    """Find git repository root or fallback to environment/current dir."""
    env_root = os.environ.get("REPO_ROOT")
    if env_root and os.path.isdir(env_root):
        return Path(env_root).resolve()

    cur = start_dir or Path.cwd()
    try:
        res = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=str(cur),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
        return Path(res.stdout.strip()).resolve()
    except Exception:
        # Walk up looking for .git
        check = cur.resolve()
        while check != check.parent:
            if (check / ".git").exists():
                return check
            check = check.parent
        return cur.resolve()


def check_dependencies() -> None:
    """Ensure required system dependencies are available."""
    missing = []
    for cmd in ["git", "python3"]:
        try:
            res = subprocess.run(
                ["which", cmd],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            if res.returncode != 0:
                missing.append(cmd)
        except Exception:
            missing.append(cmd)

    if missing:
        log_event(
            level="ERROR",
            event="DEPENDENCY_MISSING",
            message=f"Required dependencies missing: {', '.join(missing)}",
            error_code="MISSING_DEPENDENCY",
        )
        sys.exit(3)


def resolve_pinned_commit(repo_root: Path, commit_arg: Optional[str] = None) -> str:
    """Resolve target commit to a full, immutable commit hash."""
    rev = commit_arg if commit_arg else "HEAD"
    try:
        res = subprocess.run(
            ["git", "rev-parse", "--verify", f"{rev}^{{commit}}"],
            cwd=str(repo_root),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
        full_hash = res.stdout.strip()
        if not re.match(r"^[0-9a-fA-F]{40,64}$", full_hash):
            raise ValueError(f"Invalid resolved commit hash format: {full_hash}")
        return full_hash
    except Exception as e:
        log_event(
            level="ERROR",
            event="GIT_COMMIT_RESOLUTION_FAILED",
            message=f"Failed to resolve Git commit for revision '{rev}': {e}",
            error_code="GIT_ERROR",
        )
        sys.exit(1)


def parse_git_tree(repo_root: Path, pinned_commit: str) -> Dict[str, Tuple[str, str, str]]:
    """Parse git ls-tree -r -z output safely.

    Returns dict mapping path -> (mode, type, sha).
    Preserves whitespace, tabs, and newlines in filenames.
    """
    try:
        proc = subprocess.run(
            ["git", "ls-tree", "-r", "-z", pinned_commit],
            cwd=str(repo_root),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        raw_output = proc.stdout
    except Exception as e:
        log_event(
            level="ERROR",
            event="GIT_TREE_PARSING_FAILED",
            message=f"Failed to execute git ls-tree: {e}",
            error_code="GIT_ERROR",
            pinned_commit=pinned_commit,
        )
        sys.exit(1)

    tree_map: Dict[str, Tuple[str, str, str]] = {}
    records = raw_output.split(b"\x00")
    for rec in records:
        if not rec:
            continue
        if b"\t" not in rec:
            continue
        meta, path_bytes = rec.split(b"\t", 1)
        path_str = path_bytes.decode("utf-8", errors="surrogateescape")
        meta_parts = meta.split(b" ")
        if len(meta_parts) != 3:
            continue
        mode = meta_parts[0].decode("ascii", errors="replace")
        obj_type = meta_parts[1].decode("ascii", errors="replace")
        sha = meta_parts[2].decode("ascii", errors="replace")
        tree_map[path_str] = (mode, obj_type, sha)

    return tree_map


def validate_filesystem_safety(repo_root: Path, out_dir: Path) -> None:
    """Validate filesystem safety constraints:

    - Refuse unsafe output directories, including symlinks.
    - Refuse writes if output directory is on a different filesystem device than repo_root.
    """
    # 1. Check path containment
    try:
        out_resolved = out_dir.resolve()
        repo_resolved = repo_root.resolve()
        if not out_resolved.is_relative_to(repo_resolved):
            log_event(
                level="ERROR",
                event="PATH_CONTAINMENT_VIOLATION",
                message=f"Output directory {out_dir} escapes repository root {repo_root}",
                error_code="UNSAFE_OUTPUT_DIR",
            )
            sys.exit(2)
    except Exception as e:
        log_event(level="ERROR", event="FILESYSTEM_CHECK_FAILED", message=f"Path resolution failed: {e}", error_code="FS_ERROR")
        sys.exit(2)

    # 2. Check symlinks along the output directory path
    curr = out_dir
    while True:
        if curr.is_symlink():
            log_event(
                level="ERROR",
                event="SYMLINK_DIRECTORY_REFUSED",
                message=f"Symlink output directory refused: {curr}",
                error_code="UNSAFE_OUTPUT_DIR",
            )
            sys.exit(2)
        if curr == repo_root or curr == curr.parent:
            break
        curr = curr.parent

    # 3. Check filesystem device equality (cross-device check)
    existing_ancestor = out_dir
    while not existing_ancestor.exists() and existing_ancestor != existing_ancestor.parent:
        existing_ancestor = existing_ancestor.parent

    try:
        repo_stat = repo_root.stat()
        out_stat = existing_ancestor.stat()
        if repo_stat.st_dev != out_stat.st_dev:
            log_event(
                level="ERROR",
                event="CROSS_DEVICE_REFUSED",
                message=f"Cross-device output directory refused: {out_dir} (dev {out_stat.st_dev}) vs repo {repo_root} (dev {repo_stat.st_dev})",
                error_code="CROSS_DEVICE_OUTPUT",
            )
            sys.exit(2)
    except OSError as e:
        log_event(level="ERROR", event="STAT_FAILED", message=f"Failed to stat directory: {e}", error_code="FS_ERROR")
        sys.exit(2)


def durable_atomic_write(target_path: Path, content: str) -> None:
    """Perform durable, atomic write with fsync and directory sync."""
    target_path = target_path.resolve()
    parent_dir = target_path.parent

    if parent_dir.is_symlink():
        log_event(
            level="ERROR",
            event="SYMLINK_DIRECTORY_REFUSED",
            message=f"Parent directory '{parent_dir}' is a symlink. Refusing write.",
            error_code="UNSAFE_OUTPUT_DIR",
        )
        sys.exit(2)

    try:
        parent_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        log_event(level="ERROR", event="WRITE_FAILED", message=f"Cannot create parent directory {parent_dir}: {e}", error_code="FS_ERROR")
        sys.exit(2)

    if parent_dir.is_symlink():
        log_event(
            level="ERROR",
            event="SYMLINK_DIRECTORY_REFUSED",
            message=f"Parent directory '{parent_dir}' is a symlink after creation. Refusing write.",
            error_code="UNSAFE_OUTPUT_DIR",
        )
        sys.exit(2)

    tmp_path: Optional[Path] = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            dir=str(parent_dir),
            prefix=f".{target_path.name}.tmp-",
            delete=False,
            encoding="utf-8",
        ) as tmp:
            tmp_path = Path(tmp.name)
            tmp.write(content)
            tmp.flush()
            os.fsync(tmp.fileno())
            # Set restrictive file permissions (0600)
            os.chmod(tmp.name, 0o600)

        os.replace(str(tmp_path), str(target_path))
        tmp_path = None

        # Directory sync for durability
        try:
            dir_fd = os.open(str(parent_dir), os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
        except OSError:
            pass

    except OSError as e:
        log_event(level="ERROR", event="WRITE_FAILED", message=f"Failed atomic write to {target_path}: {e}", error_code="WRITE_ERROR")
        sys.exit(2)
    finally:
        if tmp_path and tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass


def load_adapter(adapter_path_or_module: Optional[str], repo_root: Path):
    """Load pluggable adapter or fallback to built-in extractor."""
    if not adapter_path_or_module:
        from adapters import example_adapter
        return example_adapter

    # Validate against path traversal or external absolute paths
    if ".." in Path(adapter_path_or_module).parts:
        log_event(
            level="ERROR",
            event="INVALID_ADAPTER_PATH",
            message=f"Path traversal rejected in --adapter: '{adapter_path_or_module}'",
            error_code="INVALID_ARGUMENTS",
        )
        sys.stderr.write(f"Error: Invalid adapter path '{adapter_path_or_module}': traversal rejected.\n")
        sys.exit(4)

    if adapter_path_or_module.startswith("/") or adapter_path_or_module.startswith("\\"):
        p_ad = Path(adapter_path_or_module).resolve()
        if not p_ad.is_relative_to(repo_root):
            log_event(
                level="ERROR",
                event="INVALID_ADAPTER_PATH",
                message=f"External absolute path rejected in --adapter: '{adapter_path_or_module}'",
                error_code="INVALID_ARGUMENTS",
            )
            sys.stderr.write(f"Error: Invalid adapter path '{adapter_path_or_module}': external absolute path rejected.\n")
            sys.exit(4)
        adapter_path_or_module = str(p_ad.relative_to(repo_root))

    adapter_file = (repo_root / adapter_path_or_module).resolve()
    if adapter_file.is_file() and adapter_file.is_relative_to(repo_root):
        spec = importlib.util.spec_from_file_location("custom_adapter", str(adapter_file))
        if spec and spec.loader:
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            if not hasattr(mod, "extract_citations"):
                log_event(level="ERROR", event="ADAPTER_MISSING_HOOK", message=f"Adapter module {adapter_file} missing 'extract_citations'", error_code="ADAPTER_ERROR")
                sys.exit(4)
            return mod

    # Attempt standard module import
    try:
        mod = importlib.import_module(adapter_path_or_module)
        if not hasattr(mod, "extract_citations"):
            log_event(level="ERROR", event="ADAPTER_MISSING_HOOK", message=f"Adapter module {adapter_path_or_module} missing 'extract_citations'", error_code="ADAPTER_ERROR")
            sys.exit(4)
        return mod
    except Exception as e:
        log_event(level="ERROR", event="ADAPTER_LOAD_FAILED", message=f"Failed to load adapter '{adapter_path_or_module}': {e}", error_code="ADAPTER_ERROR")
        sys.exit(4)


def validate_citation_record(c: Any) -> Tuple[bool, Optional[str]]:
    """Validate normalized citation candidate shape."""
    if not isinstance(c, dict):
        return False, "Citation candidate must be a dictionary"

    for req in ["target", "start_line", "end_line", "reported_in"]:
        if req not in c:
            return False, f"Missing required field: '{req}'"

    target = c["target"]
    if not isinstance(target, str) or not target.strip():
        return False, "Field 'target' must be a non-empty string"

    if target.startswith("/") or target.startswith("\\"):
        return False, f"Absolute paths not permitted in citation target: '{target}'"

    target_parts = Path(target).parts
    if ".." in target_parts:
        return False, f"Path traversal not permitted in citation target: '{target}'"

    start_line = c["start_line"]
    end_line = c["end_line"]

    if isinstance(start_line, bool) or not isinstance(start_line, int) or start_line <= 0:
        return False, f"Field 'start_line' must be a positive integer, got: {start_line!r}"

    if isinstance(end_line, bool) or not isinstance(end_line, int) or end_line < start_line:
        return False, f"Field 'end_line' must be an integer >= start_line, got: {end_line!r} (start: {start_line!r})"

    reported_in = c["reported_in"]
    if not isinstance(reported_in, str) or not reported_in.strip():
        return False, "Field 'reported_in' must be a non-empty string"

    return True, None


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit code citations in bounty reports against a pinned Git commit.",
        add_help=False,
    )
    parser.add_argument("--repo-root", help="Explicit repository root directory")
    parser.add_argument("--slug", help="Bounty slug identifier")
    parser.add_argument("--sources", help="Comma-separated or glob pattern of report files")
    parser.add_argument("--adapter", help="Python adapter module or path")
    parser.add_argument("--commit", help="Target commit identifier (defaults to HEAD)")
    parser.add_argument("--dry-run", action="store_true", help="Execute preview without writing artifacts")
    parser.add_argument("--confirm", action="store_true", help="Authorize output artifact creation and replacement")
    parser.add_argument("-h", "--help", action="store_true", help="Show usage information")

    try:
        args, unknown = parser.parse_known_args()
    except Exception as e:
        sys.stderr.write(f"Usage error: {e}\n")
        sys.exit(4)

    if args.help:
        sys.stdout.write(
            "Usage: workflow-hallucination-dropper.sh --slug SLUG [--sources GLOB[,GLOB...]] [--adapter PYTHON_MODULE] [--dry-run | --confirm]\n"
        )
        sys.exit(0)

    if unknown:
        log_event(level="ERROR", event="UNKNOWN_FLAGS_REJECTED", message=f"Unknown flags: {' '.join(unknown)}", error_code="INVALID_ARGUMENTS")
        sys.stderr.write(f"Error: Unknown flags: {' '.join(unknown)}\n")
        sys.exit(4)

    if not args.slug:
        log_event(level="ERROR", event="MISSING_SLUG", message="Option --slug is required.", error_code="INVALID_ARGUMENTS")
        sys.stderr.write("Error: Option --slug is required.\n")
        sys.exit(4)

    if not SLUG_PATTERN.match(args.slug):
        log_event(level="ERROR", event="INVALID_SLUG", message=f"Slug '{args.slug}' violates contract ^[A-Za-z0-9][A-Za-z0-9_-]{{0,99}}$", error_code="INVALID_SLUG")
        sys.stderr.write(f"Error: Slug '{args.slug}' is invalid.\n")
        sys.exit(4)

    if args.dry_run and args.confirm:
        log_event(level="ERROR", event="CONFLICTING_FLAGS", message="Cannot specify both --dry-run and --confirm.", error_code="INVALID_ARGUMENTS")
        sys.stderr.write("Error: Cannot specify both --dry-run and --confirm.\n")
        sys.exit(4)

    # Validate commit ref syntax if provided
    if args.commit and not COMMIT_REF_PATTERN.match(args.commit):
        log_event(level="ERROR", event="INVALID_COMMIT_REF", message=f"Invalid Git commit reference: '{args.commit}'", error_code="INVALID_ARGUMENTS")
        sys.stderr.write(f"Error: Invalid Git commit reference '{args.commit}'.\n")
        sys.exit(4)

    # Preview behavior is default unless --confirm is explicitly passed
    is_confirmed = args.confirm and not args.dry_run

    # Check dependencies
    check_dependencies()

    repo_root = Path(args.repo_root).resolve() if args.repo_root else find_repo_root()
    out_dir = (repo_root / "bounties" / args.slug / "scans").resolve()

    # Filesystem & directory safety validation
    validate_filesystem_safety(repo_root, out_dir)

    # Git pinned commit resolution
    pinned_commit = resolve_pinned_commit(repo_root, args.commit)

    log_event(
        level="INFO",
        event="AUDIT_START",
        message="Starting citation audit against pinned Git commit",
        slug=args.slug,
        pinned_commit=pinned_commit,
    )

    # Git tree parsing
    tree_map = parse_git_tree(repo_root, pinned_commit)

    # Discover source files
    source_files: List[str] = []
    provenance_errors: List[Dict[str, Any]] = []

    if args.sources:
        patterns = [p.strip() for p in args.sources.split(",") if p.strip()]
        for pat in patterns:
            # Validate pattern safety
            if pat.startswith("/") or pat.startswith("\\") or ".." in Path(pat).parts:
                log_event(
                    level="ERROR",
                    event="INVALID_SOURCE_PATH",
                    message=f"Absolute paths and traversal rejected in --sources: '{pat}'",
                    error_code="INVALID_ARGUMENTS",
                )
                sys.stderr.write(f"Error: Absolute paths and traversal rejected in --sources: '{pat}'\n")
                sys.exit(4)

            matched = glob.glob(str(repo_root / pat), recursive=True)
            pat_matched_count = 0
            for m in matched:
                p = Path(m).resolve()
                if p.is_file() and p.is_relative_to(repo_root):
                    rel = str(p.relative_to(repo_root))
                    if rel not in source_files:
                        source_files.append(rel)
                        pat_matched_count += 1
            if pat_matched_count == 0:
                provenance_errors.append(
                    {
                        "code": "UNMATCHED_SOURCE_PATTERN",
                        "source": pat,
                        "message": f"Source pattern '{pat}' matched zero repository files",
                    }
                )
    else:
        # Default report locations
        default_globs = [
            f"bounties/{args.slug}/findings/*.md",
            f"bounties/{args.slug}/reports/*.md",
            f"bounties/{args.slug}/*.md",
        ]
        for pat in default_globs:
            matched = glob.glob(str(repo_root / pat), recursive=True)
            for m in matched:
                p = Path(m).resolve()
                if p.is_file() and p.is_relative_to(repo_root):
                    rel = str(p.relative_to(repo_root))
                    if rel not in source_files:
                        source_files.append(rel)

    source_files.sort()

    # Load adapter
    adapter = load_adapter(args.adapter, repo_root)

    processed_count = 0
    candidate_citations: List[Dict[str, Any]] = []
    invalid_citations: List[Dict[str, str]] = []

    for src_rel in source_files:
        src_abs = repo_root / src_rel
        try:
            extracted = adapter.extract_citations(str(src_abs))
            processed_count += 1
            for c in extracted:
                valid, reason = validate_citation_record(c)
                if valid:
                    # Normalize reported_in to repository-relative path
                    rep_in = c.get("reported_in", src_rel)
                    try:
                        p_rep = Path(rep_in)
                        if p_rep.is_absolute() and p_rep.is_relative_to(repo_root):
                            rep_in = str(p_rep.relative_to(repo_root))
                        elif not p_rep.is_absolute():
                            rep_in = str(p_rep)
                    except Exception:
                        rep_in = src_rel
                    c["reported_in"] = rep_in
                    # Normalize target path
                    c["target"] = os.path.normpath(c["target"])
                    candidate_citations.append(c)
                else:
                    invalid_citations.append({"raw": repr(c), "error": reason or "Invalid format"})

                if len(candidate_citations) >= MAX_TOTAL_CITATIONS:
                    break
        except Exception as e:
            provenance_errors.append(
                {
                    "code": "ADAPTER_EXTRACTION_ERROR",
                    "source": src_rel,
                    "message": str(e),
                }
            )

    # Verification against Git tree
    verified_citations: List[Dict[str, Any]] = []
    unverified_citations: List[Dict[str, Any]] = []
    skipped_sources: List[Dict[str, str]] = []

    def add_skipped_source(src: str, reason: str) -> None:
        if not any(s["source"] == src and s["reason"] == reason for s in skipped_sources):
            skipped_sources.append({"source": src, "reason": reason})

    # Blob cache: sha -> (size, is_binary, Optional[list_of_lines])
    blob_cache: Dict[str, Tuple[int, bool, Optional[List[str]]]] = {}

    for cit in candidate_citations:
        target = cit["target"]
        start_line = cit["start_line"]
        end_line = cit["end_line"]
        reported_in = cit["reported_in"]

        if target not in tree_map:
            unverified_citations.append(
                {
                    "target": target,
                    "start_line": start_line,
                    "end_line": end_line,
                    "reported_in": reported_in,
                    "code": "FILE_NOT_FOUND",
                    "message": f"Target path '{target}' does not exist in pinned Git commit",
                }
            )
            continue

        mode, obj_type, sha = tree_map[target]

        if mode == "120000":
            unverified_citations.append(
                {
                    "target": target,
                    "start_line": start_line,
                    "end_line": end_line,
                    "reported_in": reported_in,
                    "code": "SYMLINK_TARGET",
                    "message": f"Target '{target}' is a symlink in pinned Git commit",
                }
            )
            continue

        if mode == "160000" or obj_type == "commit":
            unverified_citations.append(
                {
                    "target": target,
                    "start_line": start_line,
                    "end_line": end_line,
                    "reported_in": reported_in,
                    "code": "SUBMODULE_TARGET",
                    "message": f"Target '{target}' is a git submodule; direct blob line citations unsupported",
                }
            )
            continue

        if obj_type != "blob":
            unverified_citations.append(
                {
                    "target": target,
                    "start_line": start_line,
                    "end_line": end_line,
                    "reported_in": reported_in,
                    "code": "NON_BLOB_TARGET",
                    "message": f"Target '{target}' is not a regular blob (type={obj_type})",
                }
            )
            continue

        # Inspect blob using cache or bounded fetch
        if sha in blob_cache:
            blob_size, is_binary, lines = blob_cache[sha]
        else:
            # Query blob size first without reading full blob content
            try:
                size_proc = subprocess.run(
                    ["git", "cat-file", "-s", sha],
                    cwd=str(repo_root),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=True,
                )
                blob_size = int(size_proc.stdout.strip())
            except Exception as e:
                unverified_citations.append(
                    {
                        "target": target,
                        "start_line": start_line,
                        "end_line": end_line,
                        "reported_in": reported_in,
                        "code": "BLOB_STAT_FAILED",
                        "message": f"Failed to query size for blob {sha}: {e}",
                    }
                )
                continue

            if blob_size > MAX_BLOB_SIZE_BYTES:
                add_skipped_source(target, "BLOB_TOO_LARGE")
                blob_cache[sha] = (blob_size, False, None)
                unverified_citations.append(
                    {
                        "target": target,
                        "start_line": start_line,
                        "end_line": end_line,
                        "reported_in": reported_in,
                        "code": "BLOB_SIZE_EXCEEDED",
                        "message": f"Target '{target}' exceeds maximum allowed blob size ({blob_size} > {MAX_BLOB_SIZE_BYTES} bytes)",
                    }
                )
                continue

            if blob_size == 0:
                add_skipped_source(target, "EMPTY_BLOB")
                blob_cache[sha] = (0, False, [])
                unverified_citations.append(
                    {
                        "target": target,
                        "start_line": start_line,
                        "end_line": end_line,
                        "reported_in": reported_in,
                        "code": "EMPTY_BLOB",
                        "message": f"Target '{target}' is empty (0 lines)",
                    }
                )
                continue

            # Retrieve blob contents
            try:
                cat_proc = subprocess.run(
                    ["git", "cat-file", "blob", sha],
                    cwd=str(repo_root),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=True,
                )
                blob_bytes = cat_proc.stdout
            except Exception as e:
                unverified_citations.append(
                    {
                        "target": target,
                        "start_line": start_line,
                        "end_line": end_line,
                        "reported_in": reported_in,
                        "code": "BLOB_READ_FAILED",
                        "message": f"Failed to retrieve blob {sha} from git: {e}",
                    }
                )
                continue

            if b"\x00" in blob_bytes[:8192]:
                add_skipped_source(target, "BINARY_CONTENT")
                blob_cache[sha] = (blob_size, True, None)
                unverified_citations.append(
                    {
                        "target": target,
                        "start_line": start_line,
                        "end_line": end_line,
                        "reported_in": reported_in,
                        "code": "BINARY_SOURCE_UNSUPPORTED",
                        "message": f"Target '{target}' is binary; line citations unsupported",
                    }
                )
                continue

            text_content = blob_bytes.decode("utf-8", errors="replace")
            lines = text_content.splitlines()
            blob_cache[sha] = (blob_size, False, lines)

        # Check line citations against cached blob lines
        _, is_bin, cached_lines = blob_cache[sha]
        if is_bin:
            add_skipped_source(target, "BINARY_CONTENT")
            unverified_citations.append(
                {
                    "target": target,
                    "start_line": start_line,
                    "end_line": end_line,
                    "reported_in": reported_in,
                    "code": "BINARY_SOURCE_UNSUPPORTED",
                    "message": f"Target '{target}' is binary; line citations unsupported",
                }
            )
            continue

        if cached_lines is None:
            # Oversized or unreadable blob
            unverified_citations.append(
                {
                    "target": target,
                    "start_line": start_line,
                    "end_line": end_line,
                    "reported_in": reported_in,
                    "code": "BLOB_UNREADABLE",
                    "message": f"Target '{target}' content could not be verified",
                }
            )
            continue

        total_lines = len(cached_lines)
        if total_lines == 0:
            add_skipped_source(target, "EMPTY_BLOB")
            unverified_citations.append(
                {
                    "target": target,
                    "start_line": start_line,
                    "end_line": end_line,
                    "reported_in": reported_in,
                    "code": "EMPTY_BLOB",
                    "message": f"Target '{target}' is empty (0 lines)",
                }
            )
            continue

        if 1 <= start_line <= total_lines and start_line <= end_line <= total_lines:
            verified_citations.append(
                {
                    "target": target,
                    "start_line": start_line,
                    "end_line": end_line,
                    "reported_in": reported_in,
                    "status": "VERIFIED",
                }
            )
        else:
            unverified_citations.append(
                {
                    "target": target,
                    "start_line": start_line,
                    "end_line": end_line,
                    "reported_in": reported_in,
                    "code": "LINE_OUT_OF_BOUNDS",
                    "message": f"Line range {start_line}-{end_line} exceeds total lines ({total_lines})",
                }
            )

    citations_audited = len(verified_citations) + len(unverified_citations) + len(invalid_citations)
    dropped_count = len(unverified_citations) + len(invalid_citations)

    if citations_audited == 0:
        status_str = "NO_CITATIONS_FOUND"
        provenance_errors.append(
            {
                "code": "NO_CITATIONS_FOUND",
                "source": None,
                "message": f"No candidate citations found for slug '{args.slug}'",
            }
        )
    elif dropped_count == 0:
        status_str = "ALL_CITATIONS_VERIFIED"
    else:
        status_str = "CITATIONS_FLAGGED"

    now_ts = datetime.datetime.now(datetime.timezone.utc).isoformat()

    audit_payload = {
        "slug": args.slug,
        "pinned_commit": pinned_commit,
        "timestamp": now_ts,
        "status": status_str,
        "citations_audited": citations_audited,
        "verified_count": len(verified_citations),
        "dropped_count": dropped_count,
        "verified_citations": verified_citations,
        "unverified_citations": unverified_citations,
        "invalid_citations": invalid_citations,
        "skipped_sources": skipped_sources,
        "errors": provenance_errors,
    }

    provenance_payload = {
        "source_files": source_files,
        "processed_count": processed_count,
        "errors": provenance_errors,
        "pinned_commit": pinned_commit,
        "timestamp": now_ts,
    }

    # Dry-run / preview behavior
    if not is_confirmed:
        log_event(
            level="INFO",
            event="PREVIEW_COMPLETE",
            message=f"Preview completed: audited={citations_audited}, verified={len(verified_citations)}, dropped={dropped_count}. No files written.",
            slug=args.slug,
            pinned_commit=pinned_commit,
            processed_count=processed_count,
        )
        sys.stderr.write(
            f"[PREVIEW] Hallucination audit for '{args.slug}': {citations_audited} citations audited, {dropped_count} dropped. (No artifacts written)\n"
        )
        return 0

    # Confirmed execution: perform durable atomic writes
    audit_path = out_dir / "hallucination_audit.json"
    prov_path = out_dir / "hallucination_audit.provenance.json"

    durable_atomic_write(audit_path, json.dumps(audit_payload, ensure_ascii=False, indent=2) + "\n")
    durable_atomic_write(prov_path, json.dumps(provenance_payload, ensure_ascii=False, indent=2) + "\n")

    log_event(
        level="INFO",
        event="AUDIT_COMMITTED",
        message=f"Audit artifacts successfully written to {out_dir}",
        slug=args.slug,
        pinned_commit=pinned_commit,
        processed_count=processed_count,
    )

    if citations_audited > 0 and dropped_count == 0:
        # Emit success sentinel ONLY upon non-empty, 100% verified citations and successful writes
        sys.stdout.write("ALL_CITATIONS_VERIFIED\n")
        sys.stdout.flush()
        return 0
    else:
        # Partial verification, flagged citations, or no citations found returns exit code 1
        return 1


if __name__ == "__main__":
    sys.exit(main())
