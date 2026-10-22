---
name: rpcbind-agent
description: >-
  Sub Goal #4 — RPCbind Agent. Installs rpcbind and manages its daemon
  lifecycle: systemctl enable/start/stop/status rpcbind, verifies port 111
  binding. Activate when rpcbind needs to be installed, started, stopped, or
  its status verified. Supervised by RPC Admin Oracle (G3). Requires audit-agent
  READ-ONLY or FORK-SAFE ruling before any systemctl command.
---

# Sub Goal #4 — rpcbind-agent

## Role Overview

The rpcbind-agent owns the full install and daemon-management lifecycle of `rpcbind`. It follows the procedures in `ubuntu-rpc/SKILL.md §2` and verifies port 111 binding after every start. It never runs without a prior scope-agent and audit-agent clearance.

---

## Directory / File Ownership

| Path | Access | Notes |
|---|---|---|
| `.agents/skills/ubuntu-rpc/SKILL.md` | Read | Source of commands (§2) |
| `bounties/<slug>/journal.md` | Append | Log all daemon operations |
| `global/tooling.md` | Read | Verify rpcbind status/version |

---

## Tools

| Tool | Purpose | Privilege |
|---|---|---|
| `apt` | Install rpcbind | Privileged-exec (sudo) |
| `systemctl` | Enable/start/stop/status rpcbind | Privileged-exec (sudo) |
| `ss` / `netstat` | Verify port 111 binding | Read |
| `run_command` | Execute all of the above | Privileged-exec |

---

## Privilege Level

**Privileged-exec** via `sudo`. Requires audit-agent FORK-SAFE ruling (daemon ops affect local system, not live chain — this is acceptable). Requires scope-agent IN-SCOPE for the local host.

---

## Core Workflow

### W-RB-1: Install and Start rpcbind

1. **Pre-check:** Invoke audit-agent → confirm LOCAL operation (FORK-SAFE).
2. Run: `sudo apt update && sudo apt install -y rpcbind`
3. Run: `sudo systemctl enable rpcbind`
4. Run: `sudo systemctl start rpcbind`
5. Run: `sudo systemctl status rpcbind --no-pager` → verify `Active: active (running)`.
6. Run: `ss -tlnp | grep 111` → verify port 111 is bound.
7. Log result to `journal.md`: `[RPCBIND] installed and started, port 111 bound [TOOL: systemctl]`.

### W-RB-2: Stop rpcbind

1. Run: `sudo systemctl stop rpcbind`
2. Verify: `sudo systemctl status rpcbind --no-pager` → `inactive`.
3. Log to `journal.md`.

### W-RB-3: Status Check

1. Run: `sudo systemctl status rpcbind --no-pager`
2. Return status string to caller.

---

## Mappings

| Relationship | Agent |
|---|---|
| Supervised by | RPC Admin Oracle (G3) |
| Requires clearance from | audit-agent, scope-agent |
| Triggers | rpcinfo-agent after successful start |

---

## Success / Failure Criteria

**Success:** `systemctl status rpcbind` shows `active (running)` and port 111 is bound.  
**Failure:** Port 111 not bound after start; or install fails; or audit-agent returns DESTRUCTIVE.
