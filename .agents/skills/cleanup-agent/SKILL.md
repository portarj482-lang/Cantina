---
name: cleanup-agent
description: >-
  Sub Goal #10 — Cleanup Agent. Manages teardown, stops fork nodes, kills background
  processes, purges ephemeral secrets/keys, closes session ports, and logs session
  end to the target journal. Resolves target context via TargetContext.
  Supervised by RPC Admin Oracle (G3). Enforces INSTRUCTIONS.md Rule 7.
---

# Sub Goal #10 — cleanup-agent

## 1. Role Overview
The `cleanup-agent` is mandatory at every session and workflow termination. It enforces teardown discipline: stopping all fork nodes (Anvil, `solana-test-validator`), killing background query processes, resetting session firewall rules, and deleting ephemeral credential files. It records an auditable session termination entry in the target's `journal.md`.

---

## 2. Directory / File Ownership & Permissions
Context resolved via `TargetContext`:
- Active target journal: `context.target_root / "journal.md"`
- Ephemeral session directory: `~/.gemini/antigravity/brain/<session_id>/scratch/`

| Path | Access | Notes |
|---|---|---|
| `context.target_root / journal.md` | Append | Session end log entry |
| `context.target_root / logs/` | Read + Delete | Scan and purge ephemeral session tokens |
| `/tmp/` | Read + Delete | Temp files from RPC/test sessions |

---

## 3. Secret & Temp File Patterns (Purged on Teardown)
- `*.key`, `*.pem`, `*.env`, `*.secret`, `credentials*`, `password*`
- Private key patterns (`0x` + 64 hex characters)
- Ephemeral test sockets and lockfiles (`/tmp/rpcclient_*`, `/tmp/anvil_*`)

---

## 4. Teardown Workflow (W-CL-1)
1. **Stop Fork Nodes**: `pkill -f "anvil"`, `pkill -f "solana-test-validator"`.
2. **Kill Background Scanners**: Terminate any lingering test or query processes.
3. **Firewall Reset**: Re-lock any ephemeral ports opened during execution.
4. **Scrub Ephemeral State**: Remove temporary test wallets and secrets from disk.
5. **Log Session End**: Append timestamped teardown checklist record to target journal.

---

## 5. Result Taxonomy
- `PASS`: All background processes stopped, temp credentials scrubbed, journal logged.
- `FAIL`: Lingering background node could not be terminated or secrets unpurged.
- `BLOCKED`: Permission denied on process kill or journal write.
- `NOT_APPLICABLE`: Purely static analysis with no spawned processes.
- `NOT_VERIFIED`: Teardown status unconfirmed.
