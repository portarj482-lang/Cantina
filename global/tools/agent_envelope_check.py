#!/usr/bin/env python3
"""Check one agent response envelope against global/agents/CONTRACT.md.

Usage: python3 -I agent_envelope_check.py <envelope.json>
Exit 0: valid. Exit 1: invalid (each reason on its own line). Exit 2: bad usage or unreadable file.

Checks shape, types, status rules, citation fields, relative paths, and secret-like strings.
It does not check that a cited line exists or that a claim is true. That is the citation
checker's job (stage S8).
"""
import json
import re
import sys
from pathlib import Path

REQUIRED = ["agent", "stage", "status", "thought", "plan", "evidence", "result_files", "stop_reason"]
STATUSES = {"ok", "fail", "tool_missing", "stopped", "skipped", "no_tests"}
EVIDENCE_TYPES = {"SRC", "TOOL", "POC", "WEB", "USER", "ASSUMPTION", "UNKNOWN"}
STAGE = re.compile(r"^S(10|[1-9])$")
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
SRC_PATH = re.compile(r"^[^:\s]+:\d+$")
SECRET_PATTERNS = [
    re.compile(r"alch_[A-Za-z0-9]{8,}"),
    re.compile(r"rnd_[A-Za-z0-9]{8,}"),
    re.compile(r"https?://[^\s\"']*(alchemy|infura|quiknode|drpc)[^\s\"']*/[A-Za-z0-9_\-]{16,}", re.I),
    re.compile(r"\b0x[0-9a-fA-F]{64}\b"),  # a 0x-prefixed 64-hex value is treated as a possible private key
]


def secret_hits(raw):
    return ["secret-like value found in the envelope (A8): log SECRET_EXPOSED and stop"
            for pattern in SECRET_PATTERNS if pattern.search(raw)][:1]


def sentence_count(text):
    parts = [p for p in re.split(r"[.!?]+(?:\s+|$)", text.strip()) if p.strip()]
    return len(parts)


def nonempty_str(value):
    return isinstance(value, str) and value.strip() != ""


def check_evidence(i, item, errs):
    where = f"evidence[{i}]"
    if not isinstance(item, dict):
        errs.append(f"{where}: must be an object")
        return
    etype = item.get("type")
    if etype not in EVIDENCE_TYPES:
        errs.append(f"{where}: type must be one of {sorted(EVIDENCE_TYPES)}")
        return
    if etype == "SRC":
        if not (isinstance(item.get("path"), str) and SRC_PATH.match(item["path"])):
            errs.append(f"{where}: SRC path must be path:line")
        if not (isinstance(item.get("commit"), str) and HEX40.match(item["commit"])):
            errs.append(f"{where}: SRC commit must be a 40-hex commit")
        if not nonempty_str(item.get("quote")):
            errs.append(f"{where}: SRC needs the verbatim quote (A4)")
    elif etype in ("TOOL", "POC"):
        path = item.get("path")
        if not nonempty_str(path) or path.startswith("/") or ".." in path:
            errs.append(f"{where}: {etype} path must be relative and contain no '..'")
        if not (isinstance(item.get("sha256"), str) and HEX64.match(item["sha256"])):
            errs.append(f"{where}: {etype} needs a 64-hex sha256")
    elif etype == "WEB":
        if not (isinstance(item.get("url"), str) and item["url"].startswith("https://")):
            errs.append(f"{where}: WEB url must start with https://")
        if not (isinstance(item.get("captured"), str) and DATE.match(item["captured"])):
            errs.append(f"{where}: WEB captured must be YYYY-MM-DD")
    elif etype == "USER":
        if not nonempty_str(item.get("ref")):
            errs.append(f"{where}: USER needs ref (where the user said it)")
    else:  # ASSUMPTION or UNKNOWN
        if not nonempty_str(item.get("note")):
            errs.append(f"{where}: {etype} needs a note")


def check(env):
    errs = []
    if not isinstance(env, dict):
        return ["top level must be a JSON object"]
    missing = [k for k in REQUIRED if k not in env]
    extra = sorted(set(env) - set(REQUIRED))
    if missing:
        errs.append("missing keys: " + ", ".join(missing))
    if extra:
        errs.append("extra keys: " + ", ".join(extra))
    if missing:
        return errs

    if not nonempty_str(env["agent"]):
        errs.append("agent must be a non-empty string")
    if not (isinstance(env["stage"], str) and STAGE.match(env["stage"])):
        errs.append("stage must be S1 to S10")
    status = env["status"]
    if status not in STATUSES:
        errs.append(f"status must be one of {sorted(STATUSES)}")

    thought = env["thought"]
    if not nonempty_str(thought):
        errs.append("thought must be a non-empty string")
    elif not 1 <= sentence_count(thought) <= 3:
        errs.append(f"thought must be 1 to 3 sentences (found {sentence_count(thought)}); "
                    "put longer reasoning in a file listed under result_files")

    plan = env["plan"]
    if not isinstance(plan, list):
        errs.append("plan must be a list")
    else:
        for i, step in enumerate(plan):
            if not (isinstance(step, dict) and nonempty_str(step.get("tool")) and nonempty_str(step.get("why"))):
                errs.append(f"plan[{i}] needs tool and why")

    evidence = env["evidence"]
    if not isinstance(evidence, list):
        errs.append("evidence must be a list")
    else:
        if status == "ok" and not evidence:
            errs.append("status ok needs at least one evidence entry")
        for i, item in enumerate(evidence):
            check_evidence(i, item, errs)

    files = env["result_files"]
    if not isinstance(files, list):
        errs.append("result_files must be a list")
    else:
        for i, f in enumerate(files):
            if not nonempty_str(f) or f.startswith("/") or ".." in f.split("/"):
                errs.append(f"result_files[{i}] must be a relative path with no '..'")

    stop = env["stop_reason"]
    if status == "ok":
        if stop is not None:
            errs.append("status ok requires stop_reason null")
    elif not nonempty_str(stop):
        errs.append(f"status {status} requires a stop_reason")
    return errs


def main(argv):
    if len(argv) != 2:
        print("usage: agent_envelope_check.py <envelope.json>", file=sys.stderr)
        return 2
    path = Path(argv[1])
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"cannot read {path}: {exc}", file=sys.stderr)
        return 2
    hits = secret_hits(raw)
    if hits:
        print("INVALID")
        for h in hits:
            print(f"  - {h}")
        return 1
    try:
        env = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"INVALID\n  - not JSON: {exc}")
        return 1
    errs = check(env)
    if errs:
        print("INVALID")
        for e in errs:
            print(f"  - {e}")
        return 1
    print("VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
