"""Comprehensive test suite for bounty_orchestrator.py CLI."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path
import pytest

ORCHESTRATOR_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "bounty_orchestrator.py"


def run_cli(*args, check=False) -> subprocess.CompletedProcess:
    """Helper to run the CLI with py -3 or sys.executable."""
    cmd = [sys.executable, str(ORCHESTRATOR_SCRIPT)] + list(args)
    return subprocess.run(cmd, capture_output=True, text=True, check=check)


class TestRoute:
    def test_route_keywords(self):
        res = run_cli("route", "--target", "eip7702 delegation contract")
        assert res.returncode == 0
        assert "EIP-7702 Delegation Audit" in res.stdout

    def test_route_solidity_file(self, tmp_path):
        sol_file = tmp_path / "Hook.sol"
        sol_file.write_text(
            "contract MyHook { function beforeSwap() external returns (bytes4) {} }",
            encoding="utf-8",
        )
        res = run_cli("route", "--target", str(sol_file))
        assert res.returncode == 0
        assert "Uniswap v4 Hook Security" in res.stdout

    def test_route_standard_evm(self):
        res = run_cli("route", "--target", "standard ERC20 token")
        assert res.returncode == 0
        assert "Standard EVM Audit Vectors Activated" in res.stdout


class TestScopeLockAndVerify:
    def test_scope_lock_and_verify_no_markers(self, tmp_path):
        scope_file = tmp_path / "scope.md"
        snap_file = tmp_path / "snapshots" / "scope.sha256"
        scope_file.write_text("# In-Scope Contracts\n- 0x1234\n", encoding="utf-8")

        res_lock = run_cli(
            "scope-lock",
            "--scope-file",
            str(scope_file),
            "--snapshot-file",
            str(snap_file),
        )
        assert res_lock.returncode == 0
        assert snap_file.is_file()

        res_ver = run_cli(
            "scope-verify",
            "--scope-file",
            str(scope_file),
            "--snapshot-file",
            str(snap_file),
        )
        assert res_ver.returncode == 0
        assert "Scope integrity verified" in res_ver.stdout

    def test_scope_lock_and_verify_with_cantina_markers(self, tmp_path):
        scope_file = tmp_path / "scope.md"
        snap_file = tmp_path / "snapshots" / "scope.sha256"
        content = (
            "Intro text outside scope\n"
            "<!-- SCOPE START -->\n"
            "# Strict Scope\n"
            "- Vault.sol at 0x9999\n"
            "<!-- SCOPE END -->\n"
            "Out of scope appendix\n"
        )
        scope_file.write_text(content, encoding="utf-8")

        res_lock = run_cli(
            "scope-lock",
            "--scope-file",
            str(scope_file),
            "--snapshot-file",
            str(snap_file),
        )
        assert res_lock.returncode == 0

        # Verify passes
        res_ver = run_cli(
            "scope-verify",
            "--scope-file",
            str(scope_file),
            "--snapshot-file",
            str(snap_file),
        )
        assert res_ver.returncode == 0

        # Alter text outside marker -> still passes because marker block is unchanged
        scope_file.write_text(
            "Modified outside text\n"
            "<!-- SCOPE START -->\n"
            "# Strict Scope\n"
            "- Vault.sol at 0x9999\n"
            "<!-- SCOPE END -->\n"
            "Out of scope appendix\n",
            encoding="utf-8",
        )
        res_ver2 = run_cli(
            "scope-verify",
            "--scope-file",
            str(scope_file),
            "--snapshot-file",
            str(snap_file),
        )
        assert res_ver2.returncode == 0

        # Alter text inside marker -> fails closed!
        scope_file.write_text(
            "Intro text outside scope\n"
            "<!-- SCOPE START -->\n"
            "# Strict Scope\n"
            "- Vault.sol at 0x8888\n"
            "<!-- SCOPE END -->\n"
            "Out of scope appendix\n",
            encoding="utf-8",
        )
        res_ver3 = run_cli(
            "scope-verify",
            "--scope-file",
            str(scope_file),
            "--snapshot-file",
            str(snap_file),
        )
        assert res_ver3.returncode == 1
        assert "SCOPE MISMATCH DETECTED" in res_ver3.stdout


class TestHypothesisCycleAndKills:
    def test_hyp_cycle(self, tmp_path):
        ledger = tmp_path / "hypotheses.jsonl"

        # 1. Add hypothesis
        res_add = run_cli(
            "hyp-add",
            "--id",
            "H-001",
            "--target",
            "Vault.withdraw",
            "--actor",
            "unprivileged",
            "--prediction",
            "reverts with InsufficientBalance",
            "--ledger",
            str(ledger),
        )
        assert res_add.returncode == 0
        assert ledger.is_file()

        # 2. Kill hypothesis without category/reason -> should fail
        res_kill_invalid = run_cli(
            "hyp-status",
            "--id",
            "H-001",
            "--status",
            "killed",
            "--ledger",
            str(ledger),
        )
        assert res_kill_invalid.returncode == 1
        assert "require both --category and --reason" in res_kill_invalid.stdout

        # 3. Kill with valid category and reason -> succeeds
        res_kill_valid = run_cli(
            "hyp-status",
            "--id",
            "H-001",
            "--status",
            "killed",
            "--category",
            "reentrancy-guard",
            "--reason",
            "protected by nonReentrant modifier at line 55",
            "--ledger",
            str(ledger),
        )
        assert res_kill_valid.returncode == 0

        # 4. List hypotheses
        res_list = run_cli("hyp-list", "--ledger", str(ledger))
        assert res_list.returncode == 0
        assert "H-001" in res_list.stdout
        assert "KILLED" in res_list.stdout

        # 5. Check top kills
        res_kills = run_cli("kills", "--ledger", str(ledger))
        assert res_kills.returncode == 0
        assert "reentrancy-guard" in res_kills.stdout

        # 6. Check learn summary
        res_summary = run_cli("learn-summary", "--ledger", str(ledger))
        assert res_summary.returncode == 0
        assert "Total Unique Hypotheses Tracked: 1" in res_summary.stdout


class TestPoCAudit:
    def test_poc_audit_bare_expect_revert(self, tmp_path):
        poc_file = tmp_path / "BadPoC.t.sol"
        poc_file.write_text(
            "contract BadPoC is Test {\n"
            "    function test_Exploit() public {\n"
            "        vm.createSelectFork('rpc', 100);\n"
            "        address attacker = makeAddr('attacker');\n"
            "        vm.prank(attacker);\n"
            "        vm.expectRevert();\n"
            "        assertEq(balanceAfter - balanceBefore, delta);\n"
            "    }\n"
            "}\n",
            encoding="utf-8",
        )
        res = run_cli("poc-audit", "--poc-file", str(poc_file))
        assert res.returncode == 1
        assert "bare 'vm.expectRevert" in res.stdout

    def test_poc_audit_missing_fork_pin(self, tmp_path):
        poc_file = tmp_path / "UnpinnedPoC.t.sol"
        poc_file.write_text(
            "contract UnpinnedPoC is Test {\n"
            "    function test_Exploit() public {\n"
            "        address attacker = makeAddr('attacker');\n"
            "        vm.prank(attacker);\n"
            "        vm.expectRevert(CustomError.selector);\n"
            "        assertEq(balanceAfter - balanceBefore, delta);\n"
            "    }\n"
            "}\n",
            encoding="utf-8",
        )
        res = run_cli("poc-audit", "--poc-file", str(poc_file))
        assert res.returncode == 1
        assert "No fork block pinning" in res.stdout

    def test_poc_audit_compliant_suite(self, tmp_path):
        poc_file = tmp_path / "CompliantPoC.t.sol"
        poc_file.write_text(
            "contract CompliantPoC is Test {\n"
            "    function setUp() public {\n"
            "        vm.createSelectFork('rpc', 21000000);\n"
            "    }\n"
            "    function test_Benign() public {\n"
            "        address user = makeAddr('user');\n"
            "        vm.prank(user);\n"
            "    }\n"
            "    function test_Exploit() public {\n"
            "        address attacker = makeAddr('attacker');\n"
            "        vm.prank(attacker);\n"
            "        vm.expectRevert(CustomError.selector);\n"
            "        assertEq(balanceAfter - balanceBefore, delta);\n"
            "    }\n"
            "    function test_Boundary() public {}\n"
            "    function test_PostPatch() public {}\n"
            "}\n",
            encoding="utf-8",
        )
        res = run_cli("poc-audit", "--poc-file", str(poc_file))
        assert res.returncode == 0
        assert "PASSED PoC Structural Quality Review" in res.stdout


class TestGateAudit:
    def test_gate_audit_complete(self, tmp_path):
        bounty_dir = tmp_path / "bounties" / "test-vault"
        bounty_dir.mkdir(parents=True)
        logs_dir = bounty_dir / "logs"
        logs_dir.mkdir(parents=True)
        findings_dir = bounty_dir / "findings"
        findings_dir.mkdir(parents=True)

        scope_file = bounty_dir / "scope.md"
        scope_file.write_text("# Scope\n- Vault.sol at 0x1111222233334444\n", encoding="utf-8")

        poc_ledger = logs_dir / "poc_ledger.jsonl"
        poc_ledger.write_text('{"finding":"F-001","result":"PASS"}\n', encoding="utf-8")

        finding_file = findings_dir / "F-001.md"
        finding_file.write_text(
            "# F-001 : First depositor vault inflation\n"
            "- **Status:** Draft\n"
            "- **Bounty:** test-vault\n"
            "- **Commit:** 1234567890abcdef1234567890abcdef12345678\n"
            "- **Affected:** `Vault.withdraw` at `0x1111222233334444` [SRC: src/Vault.sol:42 @1234567890abcdef1234567890abcdef12345678]\n"
            "- **Severity (program scale):** High. Basis: Direct theft of user deposited funds.\n"
            "- **PoC:** poc/F-001_test.t.sol [POC: PASS, forge test, 2026-10-16]\n"
            "- **Duplicate check:** verified clean [WEB: https://cantina.xyz/reports, captured 2026-10-16]\n"
            "\n"
            "## Summary\n"
            "The Vault calculates share price incorrectly on first deposit. [SRC: src/Vault.sol:50 @1234567890abcdef1234567890abcdef12345678]\n"
            "\n"
            "## Root cause\n"
            "Missing dead shares minting allows dilution. [SRC: src/Vault.sol:60 @1234567890abcdef1234567890abcdef12345678]\n"
            "\n"
            "## Impact\n"
            "Attacker drains all victim deposits. [POC: PASS, forge test, 2026-10-16]\n",
            encoding="utf-8",
        )

        res = run_cli(
            "gate-audit",
            "--finding",
            str(finding_file),
            "--bounty-root",
            str(bounty_dir),
        )
        assert res.returncode == 0
        assert "6/6 GATES MET" in res.stdout

    def test_gate_audit_untagged_claim(self, tmp_path):
        bounty_dir = tmp_path / "bounties" / "test-vault"
        bounty_dir.mkdir(parents=True)
        findings_dir = bounty_dir / "findings"
        findings_dir.mkdir(parents=True)

        scope_file = bounty_dir / "scope.md"
        scope_file.write_text("# Scope\n- Vault.sol\n", encoding="utf-8")

        finding_file = findings_dir / "F-002.md"
        finding_file.write_text(
            "# F-002 : Untagged claim\n"
            "- **Status:** Draft\n"
            "- **Affected:** `Vault.sol` [SRC: src/Vault.sol:10 @1234567890abcdef1234567890abcdef12345678]\n"
            "- **Severity (program scale):** Medium\n"
            "- **PoC:** poc/F-002.t.sol [POC: PASS]\n"
            "\n"
            "## Summary\n"
            "This line has no provenance tag and makes an assertion.\n",
            encoding="utf-8",
        )

        res = run_cli(
            "gate-audit",
            "--finding",
            str(finding_file),
            "--bounty-root",
            str(bounty_dir),
        )
        assert res.returncode == 1
        assert "FAIL" in res.stdout


class TestLessonsAndCalibration:
    def test_lessons(self, tmp_path):
        lessons_file = tmp_path / "lessons.md"
        res_add = run_cli(
            "lesson-add",
            "--id",
            "L-001",
            "--text",
            "Always check sequencer uptime feed on Arbitrum",
            "--tags",
            "oracle,l2",
            "--file",
            str(lessons_file),
        )
        assert res_add.returncode == 0

        res_list = run_cli("lesson-list", "--file", str(lessons_file))
        assert res_list.returncode == 0
        assert "L-001" in res_list.stdout
        assert "sequencer uptime" in res_list.stdout

    def test_calibration(self, tmp_path):
        outcomes_file = tmp_path / "outcomes.jsonl"

        # 1. Empty file calibration does not crash
        outcomes_file.write_text("", encoding="utf-8")
        res_empty = run_cli("calibrate", "--file", str(outcomes_file))
        assert res_empty.returncode == 0
        assert "No triage outcome entries found" in res_empty.stdout

        # 2. Add outcomes with overestimation
        outcomes_file.write_text(
            json.dumps({"predicted": "High", "actual": "Medium"}) + "\n"
            + json.dumps({"predicted": "Critical", "actual": "High"}) + "\n",
            encoding="utf-8",
        )
        res_cal = run_cli("calibrate", "--file", str(outcomes_file))
        assert res_cal.returncode == 0
        assert "BIAS DETECTED: Tendency to OVERESTIMATE" in res_cal.stdout


class TestFactRecordAndEnvelopeCheck:
    def test_fact_record(self, tmp_path):
        facts_file = tmp_path / "facts.md"

        # 1. Valid fact record
        res1 = run_cli(
            "fact-record",
            "--fact",
            "Vault uses 18 decimals for asset accounting",
            "--tag",
            "[SRC: src/Vault.sol:25 @1234567890abcdef1234567890abcdef12345678]",
            "--facts-file",
            str(facts_file),
        )
        assert res1.returncode == 0
        assert "FACT-001" in facts_file.read_text(encoding="utf-8")

        # 2. Second fact record increments ID
        res2 = run_cli(
            "fact-record",
            "--fact",
            "Owner can pause withdrawals via emergencyPause()",
            "--tag",
            "[SRC: src/Vault.sol:40 @1234567890abcdef1234567890abcdef12345678]",
            "--facts-file",
            str(facts_file),
        )
        assert res2.returncode == 0
        assert "FACT-002" in facts_file.read_text(encoding="utf-8")

        # 3. Invalid tag fails
        res_bad = run_cli(
            "fact-record",
            "--fact",
            "Bad tag test",
            "--tag",
            "NO_TAG_BRACKETS",
            "--facts-file",
            str(facts_file),
        )
        assert res_bad.returncode == 1

    def test_envelope_check(self, tmp_path):
        env_file = tmp_path / "envelope.json"

        # 1. Valid envelope
        valid_data = {
            "agent": "bounty-scanner",
            "stage": "recon",
            "status": "ok",
            "thought": "Mapped all entrypoints",
            "plan": "Proceed to hypothesis cycle",
            "evidence": [
                {
                    "type": "SRC",
                    "path": "src/Vault.sol:15",
                    "commit": "1234567890abcdef1234567890abcdef12345678",
                }
            ],
            "result_files": ["facts.md"],
            "stop_reason": "stage_complete",
        }
        env_file.write_text(json.dumps(valid_data), encoding="utf-8")
        res_ok = run_cli("envelope-check", "--envelope", str(env_file))
        assert res_ok.returncode == 0
        assert "Envelope validation PASSED" in res_ok.stdout

        # 2. Invalid envelope (missing fields)
        invalid_data = {"agent": "bounty-scanner"}
        env_file.write_text(json.dumps(invalid_data), encoding="utf-8")
        res_fail = run_cli("envelope-check", "--envelope", str(env_file))
        assert res_fail.returncode == 1
        assert "Missing required field" in res_fail.stderr

    def test_envelope_check_secret_detection(self, tmp_path):
        env_file = tmp_path / "leaky_envelope.json"
        leaky_data = {
            "agent": "bounty-scanner",
            "stage": "recon",
            "status": "ok",
            "thought": "Using key alch_abcdef12345678 to scan",
            "plan": "Complete scan",
            "evidence": [],
            "result_files": [],
            "stop_reason": "done",
        }
        env_file.write_text(json.dumps(leaky_data), encoding="utf-8")
        res = run_cli("envelope-check", "--envelope", str(env_file))
        assert res.returncode == 1
        assert "SECRET_EXPOSED" in res.stderr

    def test_fact_record_large_id(self, tmp_path):
        facts_file = tmp_path / "facts.md"
        facts_file.write_text("- FACT-1000: Initial fact [SRC: a:1 @1234567890abcdef1234567890abcdef12345678]\n", encoding="utf-8")
        res = run_cli(
            "fact-record",
            "--fact",
            "Next fact after 1000",
            "--tag",
            "[SRC: a:2 @1234567890abcdef1234567890abcdef12345678]",
            "--facts-file",
            str(facts_file),
        )
        assert res.returncode == 0
        assert "FACT-1001" in facts_file.read_text(encoding="utf-8")


class TestAliasesAndEdgeCases:
    def test_hyp_set_alias(self, tmp_path):
        ledger = tmp_path / "hypotheses.jsonl"
        run_cli(
            "hyp-add",
            "--id",
            "H-100",
            "--target",
            "Pool.swap",
            "--actor",
            "unprivileged",
            "--prediction",
            "reverts",
            "--ledger",
            str(ledger),
            check=True,
        )
        res = run_cli(
            "hyp-set",
            "--id",
            "H-100",
            "--status",
            "killed",
            "--category",
            "slippage-bound",
            "--reason",
            "slippage check protects pool",
            "--ledger",
            str(ledger),
        )
        assert res.returncode == 0
        assert "status transition to 'killed'" in res.stdout

    def test_gate_check_alias_and_code_blocks(self, tmp_path):
        bounty_dir = tmp_path / "bounties" / "alias-bounty"
        bounty_dir.mkdir(parents=True)
        logs_dir = bounty_dir / "logs"
        logs_dir.mkdir(parents=True)
        findings_dir = bounty_dir / "findings"
        findings_dir.mkdir(parents=True)

        scope_file = bounty_dir / "scope.md"
        scope_file.write_text("# Scope\n- DAI.sol\n", encoding="utf-8")

        poc_ledger = logs_dir / "poc_ledger.jsonl"
        poc_ledger.write_text('{"finding":"F-003","result":"PASS"}\n', encoding="utf-8")

        finding_file = findings_dir / "F-003.md"
        finding_file.write_text(
            "# F-003 : DAI transfer fee bypass\n"
            "- **Status:** Draft\n"
            "- **Bounty:** alias-bounty\n"
            "- **Commit:** 1234567890abcdef1234567890abcdef12345678\n"
            "- **Affected:** `DAI.transfer` [SRC: src/DAI.sol:15 @1234567890abcdef1234567890abcdef12345678]\n"
            "- **Severity (program scale):** high. Basis: Direct theft.\n"
            "- **PoC:** poc/F-003.t.sol [POC: PASS, forge test, 2026-10-16]\n"
            "- **Duplicate check:** none found [WEB: https://cantina.xyz/reports, captured 2026-10-16]\n"
            "\n"
            "## Summary\n"
            "The DAI transfer function bypasses the protocol tax. [SRC: src/DAI.sol:20 @1234567890abcdef1234567890abcdef12345678]\n"
            "\n"
            "## Root Cause\n"
            "Here is the vulnerable snippet: [SRC: src/DAI.sol:25 @1234567890abcdef1234567890abcdef12345678]\n"
            "```solidity\n"
            "function transfer(address to, uint256 amount) external returns (bool) {\n"
            "    balances[to] += amount;\n"
            "    return true;\n"
            "}\n"
            "```\n"
            "\n"
            "## Impact\n"
            "Protocol loses all fee revenue. [POC: PASS, forge test, 2026-10-16]\n",
            encoding="utf-8",
        )

        res = run_cli(
            "gate-check",
            "--finding",
            str(finding_file),
            "--bounty-root",
            str(bounty_dir),
        )
        assert res.returncode == 0
        assert "6/6 GATES MET" in res.stdout

    def test_poc_audit_bare_expect_in_comment_not_failing(self, tmp_path):
        poc_file = tmp_path / "CommentPoC.t.sol"
        poc_file.write_text(
            "contract CommentPoC is Test {\n"
            "    function setUp() public {\n"
            "        vm.createSelectFork('rpc', 21000000);\n"
            "    }\n"
            "    function test_Benign() public {\n"
            "        address user = makeAddr('user');\n"
            "        vm.prank(user);\n"
            "    }\n"
            "    function test_Exploit() public {\n"
            "        // Note: do not use vm.expectRevert(); here!\n"
            "        address attacker = makeAddr('attacker');\n"
            "        vm.prank(attacker);\n"
            "        vm.expectRevert(CustomError.selector);\n"
            "        assertEq(balanceAfter - balanceBefore, delta);\n"
            "    }\n"
            "    function test_Boundary() public {}\n"
            "    function test_PostPatch() public {}\n"
            "}\n",
            encoding="utf-8",
        )
        res = run_cli("poc-audit", "--poc-file", str(poc_file))
        assert res.returncode == 0
        assert "PASSED PoC Structural Quality Review" in res.stdout

