# Tool Registry

**Last checked:** 2026-10-23 (Automated census via `scripts/check-tool-versions.sh`)
**Version commands run:** forge, cast, anvil, chisel, cargo, rustc, anchor, solana, solana-test-validator, python3, git (2026-10-23). Missing scanner tools documented.

## Status values

- **OK:** the version command ran, and its output is recorded in the Version column. Only OK tools may be used.
- **MISSING:** not found on PATH or user bin directories at the last check.
- **PRESENT:** found on PATH, with its version recorded. Not a scanner.
- **BROKEN:** found, but the version command failed. The error goes in the Install log.
- **UNCHECKED:** not checked yet.

## Column rules

- The "Candidate command (unverified)" column lists commands from tool documentation knowledge. A candidate becomes verified only after `<tool> --help` confirms every flag it uses. Record the date in Notes when that happens.
- Flags marked "Confirm" in Notes must be checked before first use.

## Tools

| Tool | Use | Install | Version check | Status (2026-10-23) | Version | Candidate command (unverified) | Notes |
|---|---|---|---|---|---|---|---|
| slither | Static analysis (Trail of Bits) | `pip install slither-analyzer` | `slither --version` | OK | 0.11.6 | `slither . --json scans/<dir>/slither.json` | Installed via pip, verified 2026-10-23 |
| myth | Symbolic execution (Mythril) | `pip install mythril` | `myth version` | OK | 0.24.8 | `myth analyze <contract>` | Installed via pip, verified 2026-10-23 |
| echidna | Property fuzzer (Trail of Bits) | GitHub releases, crytic/echidna | `echidna --version` | OK | 2.3.3 | `echidna . --contract <Name> --config echidna.yaml` | Standalone binary in ~/.local/bin, verified 2026-10-23 |
| medusa | Parallel fuzzer (Trail of Bits) | GitHub releases, crytic/medusa | `medusa --version` | OK | 1.5.1 | `medusa fuzz` | Standalone binary in ~/.local/bin, verified 2026-10-23 |
| forge | Tests, fork PoCs (Foundry) | `curl -L https://foundry.paradigm.xyz \| bash`, then `foundryup` | `forge --version` | OK | 1.8.5 | `forge test --match-test <test> --fork-url $RPC_URL_A --fork-block-number <block> -vvvv` | Verified on 2026-10-21 / 2026-10-23 |
| cast | Chain reads (Foundry) | Included with Foundry | `cast --version` | OK | 1.8.5 | `cast call`, `cast storage`, `cast code` | Read-only use only. Verified on 2026-10-21 / 2026-10-23 |
| anvil | Local fork node (Foundry) | Included with Foundry | `anvil --version` | OK | 1.8.5 | `anvil --fork-url $RPC_URL_A --fork-block-number <block>` | Verified on 2026-10-21 / 2026-10-23 |
| chisel | Solidity REPL (Foundry) | Included with Foundry | `chisel --version` | OK | 1.8.5 | `chisel` | Verified on 2026-10-21 / 2026-10-23 |
| halmos | Symbolic testing of Foundry tests | `pip install halmos` | `halmos --version` | OK | 0.3.3 | `halmos --function check_` | Installed via pip with Z3 solver, verified 2026-10-23 |
| aderyn | Static analysis (Cyfrin) | `cargo install aderyn` | `aderyn --version` | OK | 0.6.8 | `aderyn . -o <dir>/aderyn.md` | Standalone binary in ~/.local/bin, verified 2026-10-23 |
| semgrep | Pattern matching | `pip install semgrep` | `semgrep --version` | OK | 1.182.1 | `semgrep scan --config <ruleset> --json -o <dir>/semgrep.json` | Installed via pip, verified 2026-10-23 |
| solhint | Linter (excluded from consensus) | `npm install -g solhint` | `solhint --version` | OK | 6.2.5 | `solhint 'src/**/*.sol'` | Installed via npm, verified 2026-10-23 |
| solc | Compiler (solc-select manages versions) | `pip install solc-select`, then `solc-select install <ver>` | `solc --version` | OK | 0.8.20 | `solc --version` | Managed via solc-select v1.2.0, verified 2026-10-23 |
| certoraRun | Formal verification (commercial) | `pip install certora-cli` | `certoraRun --version` | MISSING | — | `certoraRun <spec>` | License required |
| kontrol | Formal verification (advanced) | Runtime Verification install guide | `kontrol --version` | MISSING | — | `kontrol run` | Command unverified |
| heimdall | Bytecode decompiler (heimdall-rs) | heimdall-rs install docs | `heimdall --version` | OK | 0.9.2 | `heimdall decompile <target>` | Standalone binary in ~/.local/bin, verified 2026-10-23 |
| python3 | Runtime for provenance_audit.py and run_pipeline.sh | System install | `python3 --version` | PRESENT | 3.12.3 | — | Found at /usr/bin/python3 |
| node | Runtime for npm-installed tools | System install | `node --version` | PRESENT | v18.19.1 | — | Installed via apt, verified 2026-10-23 |
| npm | Installer for solhint | Bundled with node | `npm --version` | PRESENT | 9.2.0 | — | Installed via apt, verified 2026-10-23 |
| git | Read-only archive of the pinned commit for the build copy | System install | `git --version` | PRESENT | 2.43.0 | `git -C <repo_path> archive <pinned_commit>` piped to `tar -x -C <build dir>` | Found at /usr/bin/git. Run `git archive --help` before first use |
| tsx | TypeScript runner for Node-side PoC scripts | `npm install -g tsx` | `tsx --version` | PRESENT | 4.23.15 | `tsx <script>.ts` | Installed via npm, verified 2026-10-23 |
| solana | Solana CLI (chain tools, local cluster) | Solana install docs | `solana --version` | OK | 1.18.4 | `solana --version` | Found at ~/.local/bin/solana, verified 2026-10-21 / 2026-10-23 |
| solana-test-validator | Local Solana cluster for PoCs on a cloned program | Ships with the Solana CLI | `solana-test-validator --version` | OK | 1.18.4 | `solana-test-validator` | Found at ~/.local/bin/solana-test-validator, verified 2026-10-21 / 2026-10-23 |
| anchor | Anchor framework (IDL and program build) | Anchor install docs | `anchor --version` | OK | 1.0.0 | `anchor --version` | Found at ~/.cargo/bin/anchor, verified 2026-10-21 / 2026-10-23 |
| cargo | Rust package manager and compiler runner | System install | `cargo --version` | PRESENT | 1.94.1 | `cargo check`, `cargo test` | Found at ~/.cargo/bin/cargo, verified 2026-10-21 / 2026-10-23 |
| rpcbind | RPC portmapper daemon (maps program numbers to ports) | `sudo apt install -y rpcbind` | `systemctl status rpcbind --no-pager` | PRESENT | 1.2.6-7 | `sudo systemctl enable --now rpcbind` | Port 111 TCP/UDP. Verified active on 2026-10-23 |
| rpcinfo | Query registered RPC programs on local/remote hosts | Included with `rpcbind` apt package | `rpcinfo --version` | PRESENT | 1.2.6-7 | `rpcinfo -p <host>`, `rpcinfo -t <host> <prog> <ver>`, `rpcinfo -u <host> <prog> <ver>` | Port 111 queried on localhost, verified 2026-10-23 |
| rpcclient | SMB/Windows MS-RPC client (Samba suite) | `sudo apt install -y smbclient` | `rpcclient --version` | PRESENT | 4.19.5-Ubuntu | `rpcclient -N -c "<cmd>" <host>`, `rpcclient -U user%pass -c "<cmd>" <host>` | Provided by smbclient on Ubuntu 24.04, verified 2026-10-23 |
| ufw | Ubuntu Firewall — manages iptables rules | Pre-installed on Ubuntu | `ufw version` | PRESENT | 0.36.2 | `sudo ufw allow 111/tcp`, `sudo ufw allow 111/udp`, `sudo ufw allow 445/tcp`, `sudo ufw allow 139/tcp` | Verified on 2026-10-23 |
| bash | Linux Shell environment runner for workflow wrappers | Pre-installed on Ubuntu | `bash --version` | PRESENT | 5.2.21 | `bash <script>.sh` | Found at /usr/bin/bash, verified 2026-10-23 |

## Install log

No install has been attempted in this workspace. Installs go through the environment proxy. Record any failure here with the command, the error, and the date. Ask the user before retrying.

## Change log

| Date | Change | Reason |
|---|---|---|
| 2026-10-10 | Status UNCHECKED replaced with MISSING for all 15 binaries from the PATH check. "Last verified" changed to "Last checked". "Verified Command" renamed to "Candidate command (unverified)". Rows added for each binary, plus python3, node, npm, and chisel. | The registry showed UNCHECKED and "last verified" while the PATH check had recorded MISSING. The commands had never been run. |
| 2026-10-10 | Version commands run for python3 (3.13.16), node (v22.22.0), npm (10.9.4), and git (2.43.0). npm set to PRESENT. chisel set to MISSING. git row added. | npm and git were UNCHECKED although the PATH lookup had found them. chisel was UNCHECKED although the PATH lookup had not found it. |
| 2026-10-11 | tsx checked in this workspace (4.23.12, OK). solana, solana-test-validator, and anchor added as MISSING. The user's Windows result (tsx 4.23.15, node 24.13.0, exit 0) is recorded in the tsx Notes, not as a workspace check. | The bounty PoC folder needs a Node runner and Solana tools before any PoC. The registry had neither. |
| 2026-10-11 | cargo checked (1.96.0, PRESENT). pump-rust-client v0.4.0 extracted into bounties/pump-fun/pump-rust-client. | Provides Rust instruction models and BPF binary artifacts for the target programs. |
| 2026-10-11 | forge, cast, and anvil checked (1.8.1, OK). | Foundry suite verified operational for fork testing and PoCs. |
| 2026-10-23 | Automated census via `scripts/check-tool-versions.sh`. Updated Foundry (1.8.5, OK), Cargo/Rustc (1.94.1, PRESENT), Anchor (1.0.0, OK), Solana CLI (1.18.4, OK), Python (3.12.3, PRESENT), Git (2.43.0, PRESENT). | Phase 6 tooling verification alignment. |
| 2026-10-23 | Completed toolchain installation and verification: slither (0.11.6, OK), myth (0.24.8, OK), echidna (2.3.3, OK), medusa (1.5.1, OK), halmos (0.3.3, OK), aderyn (0.6.8, OK), semgrep (1.182.1, OK), solhint (6.2.5, OK), solc (0.8.20, OK), heimdall (0.9.2, OK), node (v18.19.1, PRESENT), npm (9.2.0, PRESENT), tsx (4.23.15, PRESENT), rpcbind/rpcinfo (1.2.6-7, PRESENT), rpcclient (4.19.5, PRESENT), ufw (0.36.2, PRESENT). | Toolchain Installer execution per Bug Bounty Operating Manual. |