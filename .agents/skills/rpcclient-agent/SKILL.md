---
name: rpcclient-agent
description: >-
  Sub Goal #6 — RPCclient Agent. Executes rpcclient commands against authorized
  Samba/Windows targets. Manages credential handling and session state. Activate
  when SMB/Windows RPC enumeration is required against an in-scope target.
  Supervised by RPC Admin Oracle (G3). Credentials must never be stored after
  session end (INSTRUCTIONS.md Rule 7).
---

# Sub Goal #6 — rpcclient-agent

## Role Overview

The rpcclient-agent executes MS-RPC/SMB calls against authorized Samba or Windows targets using `rpcclient` (Samba suite). It follows `ubuntu-rpc/SKILL.md §4`. Credentials are handled ephemerally — never written to disk in the bounty folder. All commands are read-only enumeration unless the program explicitly authorizes write operations.

---

## Directory / File Ownership

| Path | Access | Notes |
|---|---|---|
| `.agents/skills/ubuntu-rpc/SKILL.md` | Read | Source of commands (§4) |
| `bounties/<slug>/scans/` | Write | Raw rpcclient output |
| `bounties/<slug>/journal.md` | Append | Session log |
| `bounties/<slug>/scope.md` | Read-Only | Target authorization |

---

## Tools

| Tool | Purpose | Privilege |
|---|---|---|
| `rpcclient` | SMB/Windows RPC interaction | Read (network, authorized targets) |
| `apt` | Install samba-common-bin if missing | Privileged-exec |
| `run_command` | Execute rpcclient | Exec |

---

## Privilege Level

**Read (network)** for enumeration commands. Credentials passed via `-U user%pass` flag only — never written to files. Audit class: READ-ONLY for enumeration; DESTRUCTIVE for any write operation.

---

## Credential Rules

- Credentials passed on the command line only, never in `.env` or bounty files.
- After session: verify no credential files exist in `bounties/<slug>/`.
- `cleanup-agent` must run to confirm credential purge.

---

## Core Workflow

### W-RC-1: Anonymous Enumeration

1. Scope pre-check: confirm `<target>` is IN-SCOPE.
2. Audit pre-check: READ-ONLY confirmed.
3. Run: `rpcclient -N -c "enumdomusers" <target>`
4. Save output to `bounties/<slug>/scans/<date>-rpcclient/`.
5. Log: `[RPCCLIENT] anonymous enum on <target> [TOOL: rpcclient]`.

### W-RC-2: Authenticated Enumeration

1. Scope + audit pre-checks.
2. Receive credentials from user (not stored).
3. Run: `rpcclient -U <user>%<pass> -c "<cmd>" <target>`
4. Save output (redact credentials from saved output).
5. Log (no credentials in log).
6. Invoke cleanup-agent at session end.

### W-RC-3: Install rpcclient

1. Run: `sudo apt install -y samba-common-bin`
2. Verify: `rpcclient --version`
3. Update `global/tooling.md` rpcclient row with status and version.

---

## Mappings

| Relationship | Agent |
|---|---|
| Supervised by | RPC Admin Oracle (G3) |
| Requires clearance | scope-agent, audit-agent |
| Post-session | cleanup-agent (mandatory) |
| Reports to | verification-agent |

---

## Success / Failure Criteria

**Success:** Output saved to scans/; no credentials on disk; cleanup-agent confirmed.  
**Failure:** Command run against out-of-scope target; credentials found in bounty folder after session.
