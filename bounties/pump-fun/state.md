# State: pump-fun
Updated: 2026-10-13 11:23 PT
Scope hash: 2020dd4674106963a282f9b1ffaad62b05e47aee9a8644415381775eb24cc291 (matches scope.md: yes)
Commit under review: 2293f9a66c654e9fe82dc5e8f4618538f24bb35f (pump-public-docs) & 4196facf3845d57315ef685b9a470aece190cb3e (pump-rust-client v0.4.0)
Phase: 3 (Analysis)
Status: ACTIVE
Last step: Completed Phase 3 invariant and hypothesis audit across F-001, F-002, H-003, H-004, H-005, H-006 (all verified refuted)
Next step: Awaiting reactivation or final Phase 4 report generation
Open questions:
- (On hold) In PumpSwap, can rapid interleaving of multi_hop_swap and fee sweeps cause temporary negative effective reserves if virtual reserves underflow?
Findings: F-001 (Informational / Refuted), F-002 (Informational / Refuted)
Refuted Hypotheses: H-003, H-004, H-005, H-006
Blocked on: Solana CLI toolchain (solana, solana-test-validator, anchor) marked MISSING in global/tooling.md pending user approval for install
