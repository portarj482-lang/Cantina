---
name: rpcinfo-agent
description: >-
  Sub Goal #5 — RPCinfo Agent. Runs rpcinfo -p, rpcinfo -t, and rpcinfo -u to
  discover and document all registered RPC programs on local and remote hosts.
  Activate when you need to enumerate RPC services on an authorized target.
  Supervised by RPC Admin Oracle (G3). Target must be in scope.md.
---

# Sub Goal #5 — rpcinfo-agent

## Role Overview

The rpcinfo-agent discovers and documents all registered RPC programs on local and authorized remote hosts using the `rpcinfo` tool. It follows `ubuntu-rpc/SKILL.md §3`. Every remote query requires a prior scope-agent IN-SCOPE ruling; all queries are READ-ONLY.

---

## Directory / File Ownership

| Path | Access | Notes |
|---|---|---|
| `.agents/skills/ubuntu-rpc/SKILL.md` | Read | Source of commands (§3) |
| `bounties/<slug>/scans/` | Write | Output saved as `<date>-rpcinfo/` |
| `bounties/<slug>/journal.md` | Append | Log all queries |
| `bounties/<slug>/scope.md` | Read-Only | Authorization check |

---

## Tools

| Tool | Purpose | Privilege |
|---|---|---|
| `rpcinfo` | Query RPC portmapper | Read (network) |
| `run_command` | Execute rpcinfo commands | Exec |

---

## Privilege Level

**Read (network)** — `rpcinfo` is read-only. No state changes. Audit class: READ-ONLY.

---

## Core Workflow

### W-RI-1: List Local RPC Services

1. Pre-check: audit-agent → READ-ONLY confirmed.
2. Run: `rpcinfo -p`
3. Save output to `bounties/<slug>/scans/<date>-rpcinfo/local_rpcinfo_p.txt`.
4. Parse: extract program number, version, protocol, port, service name.
5. Log to `journal.md`: `[RPCINFO] local -p query completed [TOOL: rpcinfo]`.

### W-RI-2: List Remote RPC Services

1. Pre-check: scope-agent → confirm `<target_host>` is IN-SCOPE.
2. Pre-check: audit-agent → READ-ONLY confirmed.
3. Run: `rpcinfo -p <target_host>`
4. Save to `bounties/<slug>/scans/<date>-rpcinfo/remote_<host>_rpcinfo_p.txt`.
5. Log to `journal.md` with `[SRC: bounties/<slug>/scope.md]`.

### W-RI-3: Query Specific Program via TCP/UDP

1. Scope and audit pre-checks.
2. TCP: `rpcinfo -t <host> <program_number> <version>`
3. UDP: `rpcinfo -u <host> <program_number> <version>`
4. Save results; log to journal.

---

## Mappings

| Relationship | Agent |
|---|---|
| Supervised by | RPC Admin Oracle (G3) |
| Requires clearance | scope-agent (remote queries), audit-agent |
| Depends on | rpcbind-agent (local service must be running) |
| Reports to | verification-agent |

---

## Success / Failure Criteria

**Success:** `rpcinfo -p` returns portmapper on port 111; all remote queries saved to scans/.  
**Failure:** Query against a host not in scope.md; or rpcbind not running for local query.
