---
playbook: ubuntu-rpc-multi-agent
version: 1.0.0
oracle: G3
sub-agents: [purpose-agent, scope-agent, audit-agent, rpcbind-agent, rpcinfo-agent, rpcclient-agent, network-security-agent, firewall-agent, verification-agent, cleanup-agent]
last-updated: 2026-10-21
---

# Ubuntu RPC Multi-Agent Playbook

## Purpose

This playbook orchestrates all 10 functional sub-agents under the RPC Admin Oracle (G3) to safely install, configure, discover, and interact with RPC services on Ubuntu. Every workflow is non-destructive by default (INSTRUCTIONS.md Rule 2) and operates only against targets listed in `bounties/<slug>/scope.md` (Rule 1).

## Scope

**In-scope:** Local Ubuntu host RPC configuration; remote RPC discovery against hosts explicitly listed in `bounties/<slug>/scope.md`; SMB/Windows RPC enumeration against authorized Samba/Windows targets.

**Out-of-scope:** Any host not in scope.md; live mainnet state-changing operations; storing credentials on disk; running RPC queries outside of an active bounty session.

---

## Sub-Goal Index

### Sub Goal #1: purpose-agent — Define Purpose Before Writing

**Agent SKILL.md:** `.agents/skills/purpose-agent/SKILL.md`

#### Tools
- `read_file`, `grep_search`, `write_file`

#### Scope Constraints
- Read-only on existing artifacts; writes only to `## Purpose` sections.

#### Workflow Steps
1. Receive the artifact type and description from the calling oracle.
2. Search existing SKILL.md files and `global/agents/index.md` for duplicate purposes.
3. Write a 2–4 sentence Purpose Statement (what problem, who activates, what is out of scope).
4. Confirm the statement before any further writing.

#### Verification Steps
- Confirm the created artifact has a non-empty `## Purpose` section.
- `verification-agent` checks the purpose is tagged `[SRC: purpose-agent]`.

#### Success / Failure Criteria
- **Success:** Every artifact created this session has an approved Purpose Statement on record.
- **Failure:** Any artifact written without a Purpose Statement.

---

### Sub Goal #2: scope-agent — Authorize Every Target

**Agent SKILL.md:** `.agents/skills/scope-agent/SKILL.md`

#### Tools
- `read_file` (scope.md, MEMORY.md), `grep_search`

#### Scope Constraints
- Read-only; never writes to bounty folders.

#### Workflow Steps
1. Read `MEMORY.md` → identify active bounty slug.
2. Read `bounties/<slug>/scope.md`.
3. Search for the target (host/IP/address) in scope.md.
4. Return IN-SCOPE / OUT-OF-SCOPE / AMBIGUOUS ruling with `[SRC: bounties/<slug>/scope.md]`.
5. Log ruling to `bounties/<slug>/journal.md`.

#### Verification Steps
- `verification-agent` confirms the ruling tag cites the correct scope.md path.
- No RPC command may proceed without a logged IN-SCOPE ruling.

#### Success / Failure Criteria
- **Success:** All targets validated; rulings logged before any connection.
- **Failure:** Any connection to a host without a prior IN-SCOPE ruling.

---

### Sub Goal #3: audit-agent — Enforce Non-Destructive Use

**Agent SKILL.md:** `.agents/skills/audit-agent/SKILL.md`

#### Tools
- `read_file`, `grep_search`, `write_file` (append to journal.md)

#### Scope Constraints
- No exec privilege; classifies commands only.

#### Workflow Steps
1. Receive the proposed command.
2. Parse for state-changing flags (`--send`, `write`, `add`, `create`, `modify`, `delete`).
3. Check if target is live mainnet or production host.
4. Return READ-ONLY / FORK-SAFE / DESTRUCTIVE classification.
5. Log `[AUDIT] <date> <command> → <classification>` to `journal.md`.
6. If DESTRUCTIVE: hard BLOCK; do not proceed.

#### Verification Steps
- `verification-agent` checks every executed command has an audit log entry.
- audit-agent ruling must precede any rpcbind-agent or rpcclient-agent exec.

#### Success / Failure Criteria
- **Success:** Every executed command has a logged READ-ONLY or FORK-SAFE ruling.
- **Failure:** Any state-changing command executed without a FORK-SAFE ruling.

---

### Sub Goal #4: rpcbind-agent — Install & Daemon Management

**Agent SKILL.md:** `.agents/skills/rpcbind-agent/SKILL.md`

#### Tools
- `apt` (install), `systemctl` (enable/start/stop/status), `ss` (port verification), `run_command`

#### Scope Constraints
- Local host only; requires audit-agent FORK-SAFE ruling (local daemon — acceptable).

#### Workflow Steps
1. Pre-checks: audit-agent → FORK-SAFE; scope-agent → local host OK.
2. `sudo apt update && sudo apt install -y rpcbind`
3. `sudo systemctl enable rpcbind`
4. `sudo systemctl start rpcbind`
5. `sudo systemctl status rpcbind --no-pager` → verify `active (running)`.
6. `ss -tlnp | grep 111` → verify port 111 bound.
7. Log: `[RPCBIND] installed and started, port 111 bound [TOOL: systemctl]`.

#### Verification Steps
- `verification-agent` confirms: `systemctl status` output shows `active`; port 111 in `ss` output.
- Log entry present in `journal.md`.

#### Success / Failure Criteria
- **Success:** rpcbind running, port 111 bound, log entry present.
- **Failure:** Port 111 not bound; or audit-agent returns DESTRUCTIVE; or service fails to start.

---

### Sub Goal #5: rpcinfo-agent — Service Verification & Listing

**Agent SKILL.md:** `.agents/skills/rpcinfo-agent/SKILL.md`

#### Tools
- `rpcinfo` (`-p`, `-t`, `-u`), `run_command`

#### Scope Constraints
- Remote queries require scope-agent IN-SCOPE ruling for the target host.
- All queries are READ-ONLY (audit-agent classification).

#### Workflow Steps
1. Pre-checks: scope-agent IN-SCOPE (remote); audit-agent READ-ONLY.
2. Local: `rpcinfo -p` → save to `bounties/<slug>/scans/<date>-rpcinfo/local_rpcinfo_p.txt`.
3. Remote: `rpcinfo -p <target_host>` → save to `bounties/<slug>/scans/<date>-rpcinfo/remote_<host>_rpcinfo_p.txt`.
4. TCP probe: `rpcinfo -t <host> <prog_num> <version>`.
5. UDP probe: `rpcinfo -u <host> <prog_num> <version>`.
6. Log all queries to `journal.md` with `[TOOL: rpcinfo]`.

#### Verification Steps
- `verification-agent` checks: output file exists; portmapper (program 100000) appears on port 111.
- Scope ruling tag `[SRC: bounties/<slug>/scope.md]` present in log.

#### Success / Failure Criteria
- **Success:** Output saved; portmapper visible on port 111; all remote queries against in-scope hosts.
- **Failure:** Query against out-of-scope host; rpcbind not running; output file missing.

---

### Sub Goal #6: rpcclient-agent — SMB RPC Interaction

**Agent SKILL.md:** `.agents/skills/rpcclient-agent/SKILL.md`

#### Tools
- `rpcclient` (Samba suite), `apt` (install), `run_command`

#### Scope Constraints
- Target must be in scope.md; credentials never written to disk; cleanup-agent runs after every session.

#### Workflow Steps
1. Pre-checks: scope-agent IN-SCOPE; audit-agent READ-ONLY; network-security-agent VALIDATED.
2. If not installed: `sudo apt install -y samba-common-bin` → verify `rpcclient --version`.
3. Anonymous: `rpcclient -N -c "<cmd>" <target>` → save to `scans/<date>-rpcclient/`.
4. Authenticated: `rpcclient -U <user>%<pass> -c "<cmd>" <target>` → save (redact credentials).
5. Log: `[RPCCLIENT] <cmd> on <target> [TOOL: rpcclient]`.
6. Invoke cleanup-agent at session end.

#### Verification Steps
- `verification-agent` confirms: output file exists; no credentials in journal.md or scan files.
- cleanup-agent SESSION END entry present in `journal.md`.

#### Success / Failure Criteria
- **Success:** Output saved; credentials purged; cleanup confirmed.
- **Failure:** Out-of-scope target; credentials found on disk after session.

---

### Sub Goal #7: network-security-agent — Networking Security

**Agent SKILL.md:** `.agents/skills/network-security-agent/SKILL.md`

#### Tools
- `dig`, `nslookup`, `ping`, `ip route`, `run_command`

#### Scope Constraints
- Passive inspection only (READ-ONLY); no network writes.

#### Workflow Steps
1. Receive hostname or IP from calling agent.
2. `dig +short <hostname>` → resolve to IP.
3. Invoke scope-agent with resolved IP → IN-SCOPE / BLOCKED.
4. `ip route get <ip>` → confirm expected gateway.
5. Return VALIDATED / BLOCKED.
6. Log: `[NETWORK] <host> → <ip> → <ruling> [TOOL: dig]`.

#### Verification Steps
- `verification-agent` checks: DNS resolution logged; scope ruling present; no BLOCKED host connected.

#### Success / Failure Criteria
- **Success:** All hosts resolve and are IN-SCOPE before connection.
- **Failure:** Connection to BLOCKED IP; DNS failure not surfaced before connection.

---

### Sub Goal #8: firewall-agent — Firewall Security

**Agent SKILL.md:** `.agents/skills/firewall-agent/SKILL.md`

#### Tools
- `ufw` (status, allow, delete), `run_command`

#### Scope Constraints
- No port opened without Oracle authorization; every change logged before execution.

#### Workflow Steps
1. Pre-session audit: `sudo ufw status verbose` → parse open/closed ports.
2. Report state to RPC Admin Oracle.
3. On authorization: log intent → `sudo ufw allow <port>/<proto>` → verify rule.
4. At session end (invoked by cleanup-agent): `sudo ufw delete allow <port>/<proto>` for each opened port.
5. Log: `[FIREWALL] opened/closed <port>/<proto> [TOOL: ufw]`.

#### Verification Steps
- `verification-agent` checks: firewall log entries precede any rpcinfo/rpcclient exec.
- Post-session: verify closed ports via `sudo ufw status verbose`.

#### Success / Failure Criteria
- **Success:** All session ports closed at end; every change logged; no unauthorized port opened.
- **Failure:** Port left open after session; change executed without prior log entry.

---

### Sub Goal #9: verification-agent — Independent Verification

**Agent SKILL.md:** `.agents/skills/verification-agent/SKILL.md`

#### Tools
- `read_file`, `grep_search`, `write_file` (finding annotation)

#### Scope Constraints
- Read-only on source files; annotates findings only — does not rewrite evidence.

#### Workflow Steps
1. Receive claim and provenance tag from sub-agent.
2. Open cited source file (`[SRC:]` → file, `[TOOL:]` → scan output).
3. `grep_search` for claim text in source.
4. If found: annotate `[VERIFIED: <tag>]`; if not: annotate `[UNVERIFIED]` → block submission.
5. Log: `[VERIFY] <claim> → <result> [SRC: verification-agent]`.
6. Pre-submission: run W-VA-2 on all findings; emit SUBMISSION-READY or BLOCKED.

#### Verification Steps
- verification-agent is self-verifying: its log entries must cite specific source files and line numbers.

#### Success / Failure Criteria
- **Success:** All finding claims `[VERIFIED]`; SUBMISSION-READY emitted.
- **Failure:** Any `[ASSUMPTION]` or `[UNVERIFIED]` reaching submission.

---

### Sub Goal #10: cleanup-agent — Clean-up Procedures

**Agent SKILL.md:** `.agents/skills/cleanup-agent/SKILL.md`

#### Tools
- `pkill`, `kill`, `systemctl stop`, `ufw` (via firewall-agent), `find`, `rm`, `run_command`

#### Scope Constraints
- May delete only session-created temp files and secret-pattern files; never deletes bounty evidence files.

#### Workflow Steps
1. `pkill -f "anvil"` → verify no anvil processes.
2. `pkill -f "rpcinfo"`, `pkill -f "rpcclient"`.
3. Invoke `firewall-agent W-FA-3` → close all session-opened ports.
4. If rpcbind started this session: `sudo systemctl stop rpcbind`.
5. Secret sweep: `find /tmp -name "*.key" -o -name "*.env" | xargs rm -f`.
6. Sweep bounty folder: `find bounties/<slug>/ -name "credentials*" | xargs rm -f`.
7. Verify: re-run find → confirm empty.
8. Log SESSION END entry to `journal.md`.

#### Verification Steps
- `verification-agent` checks: SESSION END entry in journal.md; no secret files; no open ports.

#### Success / Failure Criteria
- **Success:** SESSION END logged; no secrets; no open ports; no background RPC processes.
- **Failure:** Session ends without cleanup-agent running; any item from the checklist missed.

---

## Changelog

| Version | Date | Change |
|---|---|---|
| 1.0.0 | 2026-10-21 | Initial creation — all 10 sub-agent workflow sections. |
