# Tool Install Log

**Workspace:** `/home/nova/projects/cantina`  
**Host:** Ubuntu 24.04 LTS (x86_64)  
**Lead:** Toolchain Installer and Environment Lead  
**Audit Standard:** Cantina Bug Bounty Operating Manual Section 7.1 & Provenance Requirements  

---

## 1. Preflight Backup
- **Timestamp:** 2026-10-23T07:35:49Z
- **Backup Directory:** `maintenance/backups/toolchain-20261023T073549Z/`
- **Preserved Artifacts:**
  - `~/.bashrc`
  - `~/.profile`
  - `~/.cargo/env`
  - `global/tooling.md`
- **Verification:** Directory created and files verified intact before modifying environment or system configs.

---

## 2. System and Host Package Installations

### nodejs and npm
- **Command:** `sudo apt-get update -y && sudo apt-get install -y nodejs npm`
- **Date:** 2026-10-23T07:38:12Z
- **Status:** SUCCESS
- **Verification Outputs:**
  - `node --version`: `v18.19.1`
  - `npm --version`: `9.2.0`
- **Binary Paths:** `/usr/bin/node`, `/usr/bin/npm`
- **Notes:** Host package repository provides Node.js v18 LTS and npm v9.

### python3-pip and python3.12-venv
- **Command:** `sudo apt-get install -y python3-pip python3.12-venv`
- **Date:** 2026-10-23T07:38:30Z
- **Status:** SUCCESS
- **Verification Outputs:**
  - `pip --version`: `pip 24.0 from /usr/lib/python3/dist-packages/pip (python 3.12)`
- **Binary Path:** `/usr/bin/pip3`
- **Notes:** Enables user package installs via `--break-system-packages` per PEP 668 and virtual environment provisioning.

### rpcbind and rpcinfo
- **Command:** `sudo apt-get install -y rpcbind`
- **Date:** 2026-10-23T07:39:05Z
- **Status:** SUCCESS
- **Verification Outputs:**
  - `rpcbind -v`: `rpcbind: invalid option -- 'v'` (version 1.2.6-7 via dpkg)
  - `rpcinfo -p 127.0.0.1`: `100000 4 tcp 111 portmapper`
- **Binary Paths:** `/usr/sbin/rpcbind`, `/usr/sbin/rpcinfo`
- **Notes:** Daemon installed and service verified binding port 111. Supervised by rpc-admin-oracle and rpcbind-agent.

### rpcclient (via smbclient)
- **Command:** `sudo apt-get install -y smbclient`
- **Date:** 2026-10-23T07:39:40Z
- **Status:** SUCCESS
- **Verification Outputs:**
  - `rpcclient --version`: `Version 4.19.5-Ubuntu`
- **Binary Path:** `/usr/bin/rpcclient`
- **Notes:** On Ubuntu 24.04 (Noble), `rpcclient` is provided by `smbclient` package rather than `samba-common-bin`. Verified functional.

### ufw (Ubuntu Firewall)
- **Command:** `sudo apt-get install -y ufw`
- **Date:** 2026-10-23T07:40:02Z
- **Status:** SUCCESS
- **Verification Outputs:**
  - `ufw version`: `ufw 0.36.2`
- **Binary Path:** `/usr/sbin/ufw`
- **Notes:** Firewall package present; rules for ports 111, 445, 139 managed exclusively by firewall-agent.

---

## 3. Node Global Package Installations

### solhint
- **Command:** `sudo npm install -g solhint`
- **Date:** 2026-10-23T07:41:15Z
- **Status:** SUCCESS
- **Verification Outputs:**
  - `solhint --version`: `6.2.5`
- **Binary Path:** `/usr/local/bin/solhint`
- **Notes:** Solidity linter installed globally; operational for static checking.

### tsx
- **Command:** `sudo npm install -g tsx`
- **Date:** 2026-10-23T07:41:35Z
- **Status:** SUCCESS
- **Verification Outputs:**
  - `tsx --version`: `tsx v4.23.15`
- **Binary Path:** `/usr/local/bin/tsx`
- **Notes:** TypeScript execution engine for Node-side PoCs and scripts.

---

## 4. Pre-existing Verified Toolchain Matrix

| Tool | Verified Version | Binary Location | Verification Date |
|---|---|---|---|
| `forge` | 1.8.5 | `/home/nova/.foundry/bin/forge` | 2026-10-21 / 2026-10-23 |
| `cast` | 1.8.5 | `/home/nova/.foundry/bin/cast` | 2026-10-21 / 2026-10-23 |
| `anvil` | 1.8.5 | `/home/nova/.foundry/bin/anvil` | 2026-10-21 / 2026-10-23 |
| `chisel` | 1.8.5 | `/home/nova/.foundry/bin/chisel` | 2026-10-21 / 2026-10-23 |
| `cargo` | 1.94.1 | `/home/nova/.cargo/bin/cargo` | 2026-10-21 / 2026-10-23 |
| `rustc` | 1.94.1 | `/home/nova/.cargo/bin/rustc` | 2026-10-21 / 2026-10-23 |
| `anchor` | 1.0.0 | `/home/nova/.cargo/bin/anchor` | 2026-10-21 / 2026-10-23 |
| `solana` | 1.18.4 | `/home/nova/.local/bin/solana` | 2026-10-21 / 2026-10-23 |
| `solana-test-validator` | 1.18.4 | `/home/nova/.local/bin/solana-test-validator` | 2026-10-21 / 2026-10-23 |
| `python3` | 3.12.3 | `/usr/bin/python3` | 2026-10-21 / 2026-10-23 |
| `git` | 2.43.0 | `/usr/bin/git` | 2026-10-21 / 2026-10-23 |

---


## 5. Python Security Packages Installed

### slither-analyzer & solc-select
- **Command:** `python3 -m pip install --user --break-system-packages slither-analyzer`
- **Date:** 2026-10-23T07:53:44Z
- **Status:** SUCCESS
- **Verification Outputs:**
  - `slither --version`: `0.11.6`
  - `solc-select --help`: v1.2.0 functional
  - `solc-select install 0.8.20 && solc-select use 0.8.20`: `solc Version: 0.8.20+commit.a1b79de6.Linux.g++`
- **Binary Paths:** `~/.local/bin/slither`, `~/.local/bin/solc-select`, `~/.local/bin/solc`
- **Notes:** Primary static analysis engine for EVM contracts.

### halmos (Symbolic Testing)
- **Command:** `python3 -m pip install --user --break-system-packages halmos`
- **Date:** 2026-10-23T07:58:53Z
- **Status:** SUCCESS
- **Verification Outputs:**
  - `halmos --version`: `halmos 0.3.3`
  - Bundled with `z3-solver` and `yices-solver`.
- **Binary Path:** `~/.local/bin/halmos`
- **Notes:** Symbolic property testing engine for Foundry tests.

### semgrep (Pattern Matching)
- **Command:** `python3 -m pip install --user --break-system-packages semgrep`
- **Date:** 2026-10-23T08:04:47Z
- **Status:** SUCCESS
- **Verification Outputs:**
  - `semgrep --version`: `1.182.1`
- **Binary Path:** `~/.local/bin/semgrep`
- **Notes:** AST pattern matching and vulnerability rule scanner.

### mythril (Symbolic Execution)
- **Command:** `python3 -m pip install --user --break-system-packages mythril`
- **Date:** 2026-10-23T08:17:53Z
- **Status:** SUCCESS
- **Verification Outputs:**
  - `myth version`: `Mythril version v0.24.8`
- **Binary Path:** `~/.local/bin/myth`
- **Notes:** Symbolic execution security analyzer for EVM bytecode.

---

## 6. Standalone Scanner Binaries Installed

### echidna (Property Fuzzer)
- **Release Source:** crytic/echidna v2.3.3 (`echidna-2.3.3-x86_64-linux.tar.gz`)
- **Date:** 2026-10-23T08:05:52Z
- **Status:** SUCCESS
- **Verification Outputs:**
  - `echidna --version`: `Echidna 2.3.3`
- **Binary Path:** `~/.local/bin/echidna`
- **Notes:** Trail of Bits property-based fuzzer.

### medusa (Parallel Fuzzer)
- **Release Source:** crytic/medusa v1.5.1 (`medusa-linux-x64.tar.gz`)
- **Date:** 2026-10-23T08:05:52Z
- **Status:** SUCCESS
- **Verification Outputs:**
  - `medusa --version`: `medusa version 1.5.1`
- **Binary Path:** `~/.local/bin/medusa`
- **Notes:** Go-based parallel fuzzing engine.

### aderyn (Static Analyzer)
- **Release Source:** Cyfrin/aderyn v0.6.8 (`aderyn-x86_64-unknown-linux-gnu.tar.xz`)
- **Date:** 2026-10-23T08:05:52Z
- **Status:** SUCCESS
- **Verification Outputs:**
  - `aderyn --version`: `aderyn 0.6.8`
- **Binary Path:** `~/.local/bin/aderyn`
- **Notes:** Rust-based static analyzer from Cyfrin.

### heimdall (Bytecode Decompiler)
- **Release Source:** Jon-Becker/heimdall-rs v0.9.3 (`heimdall-linux-amd64`)
- **Date:** 2026-10-23T08:08:26Z
- **Status:** SUCCESS
- **Verification Outputs:**
  - `heimdall --version`: `heimdall 0.9.2`
- **Binary Path:** `~/.local/bin/heimdall`
- **Notes:** Advanced EVM smart contract decompiler and bytecode analysis toolkit.

### typescript (tsc Compiler)
- **Command:** `sudo npm install -g typescript`
- **Date:** 2026-10-23T08:12:42Z
- **Status:** SUCCESS
- **Verification Outputs:**
  - `tsc --version`: `Version 7.0.2`
- **Binary Path:** `/usr/local/bin/tsc`
- **Notes:** Required for compiling TypeScript types and Security Mesh packages.

---

## 7. Automated Tooling Census Verification

Full automated census executed via `./scripts/check-tool-versions.sh --out maintenance/reports/tool-versions.json`:
- **11 Verified Operational Security Scanners / Compilers:** `forge`, `anchor`, `slither`, `aderyn`, `semgrep`, `halmos`, `myth`, `echidna`, `medusa`, `solhint`, `heimdall`
- **13 Verified Present Host / Runtime Tools:** `cast`, `anvil`, `chisel`, `cargo`, `rustc`, `solana`, `solana-test-validator`, `python3`, `git`, `node`, `npm`, `tsx`, `solc`
- **4 Verified System RPC & Security Daemons:** `rpcbind`, `rpcinfo`, `rpcclient`, `ufw`
- **2 Excluded / Proprietary:** `certoraRun` (commercial license required), `kontrol` (formal verification platform)
