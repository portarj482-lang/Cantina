# Journal: pump-fun

## 2026-10-10 23:18 PT | SWITCH IN
- What: Initialized bounty pump-fun from Cantina program overview.
- Files: scope.md, state.md, facts.md, .gemini/BOUNTY_MANIFEST.json, .gemini/GEMINI.md
- Result: Scope locked with SHA-256 a729128a34fcff610fd376da38f4de0cac2a68a63e522fa607718a04c58bdc33.
- Next: Clone public docs and inspect devnet contracts/IDLs.

## 2026-10-10 23:20 PT | RECON
- What: Cloned pump-public-docs repository; verified matching IDLs for Pump, Pump Fees, and Pump AMM.
- Files: pump-public-docs/idl/pump.json, pump-public-docs/idl/pump_fees.json, pump-public-docs/idl/pump_amm.json
- Result: Contract addresses in IDLs match in-scope Devnet addresses exactly.
- Next: Move to Phase 2 (Reconnaissance and Tooling) — generate threat model (W1) and contract entrypoint maps.

## 2026-10-10 23:26 PT | THREAT MODEL
- What: Completed W1 model-first reconnaissance and formulated threat_model.md.
- Files: threat_model.md, artifacts/implementation_plan.md, facts.md, state.md
- Result: 10 core invariants (INV-001 - INV-010) identified across synthetic migration, negative virtual quote reserves, and fee sweeps.
- Next: Phase 3 Hypothesis generation (W6) and targeted vulnerability probing.

## 2026-10-10 23:40 PT | AGENT SET INSTALLED
- What: Added Cantina Agent Set v1.0. Created CONTRACT.md and all 36 specialized agent definitions.
- Files: global/agents/CONTRACT.md, global/agents/*.md (36 files), global/tooling.md (git registered as OK), BOUNTY_MANIFEST.json (analysis block configured)
- Result: All 36 pipeline and stage agents ready under fail-closed contract.
- Next: Proceed with Phase 3 Analysis / Hypothesis Testing (W6) on pump-fun.

## 2026-10-14 13:55 PT | TECHNICAL REVIEW
- What: Corrected evidence descriptions for F-001 and F-002 and downgraded unsupported protocol claims from local hypothesis harnesses.
- Files: findings/F-001.md, findings/F-002.md, facts.md, state.md
- Result: The recorded TypeScript runs are offline models/calculations, not target-program executions. The saved gate JSON is a provenance scan only, not a six-gate readiness result. Bounty analysis remains paused.
- Next: Await explicit instruction to resume; establish an authorized Devnet verification method before making claims about deployed behavior.
