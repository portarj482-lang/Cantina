# Bounty tool catalog

Use this catalog through `$smart-contract-bounties`. The local scripts remain in their owning folders; this skill is the router, not a duplicate copy. Prefer one helper per operation and read that helper's `--help` before using unfamiliar options.

## Local tools

| Need | Tool | What it does / limits |
|---|---|---|
| Route a target; manage hypotheses, facts, run records, evidence manifests, audits, and retrospective data | `py -3 .agents/skills/smart-contract-bounties/scripts/bounty_orchestrator.py <command>` | Main multi-platform CLI. Run `--help` for commands. Some commands write append-only bounty records or reports. |
| Cantina-specific scope, envelope, fact, or gate helper | `py -3 .agents/skills/cantina-bug-bounty/scripts/bounty_cli.py <command>` | Cantina compatibility CLI. It overlaps several orchestrator commands; don't run both for the same write. Gate checks are diagnostic, not proof or authorization. |
| Audit finding prose for provenance tags and banned wording | `py -3 global/tools/provenance_audit.py bounties/<slug>/findings` | Read-only shape/content heuristic. It does not validate citations or establish claim truth. Requires at least one `F-*.md` file. |
| Validate a structured agent response | `py -3 global/tools/agent_envelope_check.py <envelope.json>` | Checks envelope shape, types, citation fields, and secret-like strings. It does not validate that citations are accurate. |
| Validate a portable evidence graph and its artifact hashes | `py -3 global/core/case_state.py --case bounties/<slug>/artifacts/case-state.json --bounty-root bounties/<slug> [--parent <previous.json>]` | Checks scope anchor, safe paths, artifact hashes, graph structure, and supplied parent linkage. It does not prove a finding or create snapshots. |
| Run a local verification/build/scan/fuzz/PoC/gate stage | `bash global/tools/run_pipeline.sh <slug> <stage>` | Writes scan/log artifacts and may run tools or fork-based PoCs. Only use when the user requests that stage, the active bounty and scope are verified, the build copy and tooling are approved, and required inputs are pinned. PoC stages use RPC URLs from environment variables; never expose their values. Never run against live contracts. |

## Choose the least powerful fitting command

- **Read-only review:** `route`, `hyp-list`, `kills`, `lesson-list`, `run-verify`, `run-observe`, `fact-review`, `evidence-verify`, `provenance_audit.py`, `agent_envelope_check.py`, or `case_state.py`.
- **Record a user-authorized workflow result:** `hyp-add`/`hyp-status`, `fact-record`, `run-record`, `lesson-add`, and `outcome-add` append records; evidence sealing and report commands write files. Keep output inside the active bounty.
- **Run a test or scanner:** the pipeline runner is a state-changing execution tool. Ask for any missing authorization or pin, check `global/tooling.md` and the active scope first, and stop on mismatches. A scanner result or test `PASS` is a lead/result, not a validated vulnerability.
- **Finding readiness:** use `poc-audit`, `gate-check`, or `workflow-preflight` as diagnostics, then manually inspect the saved source, PoC, outputs, scope, duplicates, and impact. Only the user can approve or submit.

The main CLI and Cantina CLI have overlapping commands. Use the main CLI by default for the unified workflow; choose the Cantina CLI when its platform-specific interface is required. Do not repeat a write through both CLIs just to obtain duplicate logs.

## Specialist references

- [End-to-end workflow router](workflow_router.md)
- [PoC standards](foundry_poc_standards.md)
- [Hypothesis kill taxonomy](kill_taxonomy.md)
- [Domain attack patterns](domain_attack_vectors.md)
- [Cantina workflow and constraints](../../cantina-bug-bounty/SKILL.md)
- [Cantina vulnerability checklist](../../cantina-bug-bounty/references/vulnerability_checklist.md)
- [Cantina finding template](../../cantina-bug-bounty/references/finding_template.md)
- [Agent contract and response-envelope rules](../../../../global/agents/CONTRACT.md)

Use the platform-specific or domain reference only when that mode applies; the master skill is the single entry point, not a reason to load every guide or run every tool.
