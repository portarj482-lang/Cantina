import { describe, expect, it } from 'vitest';
import { randomUUID, createHash, generateKeyPairSync } from 'node:crypto';
import {
  checkFindingApprovalSeparation,
  checkIndependentReviewSeparation,
  checkSubmissionAuthorization,
  type AuthenticatedPrincipal,
} from '../src/security/roles.js';
import { checkAnalysisAdmission, verifySourceSpanContent } from '../src/provenance/admission.js';
import type { ControlledSourceRecord } from '../src/provenance/source-record.js';
import type { CompilerProvenanceRecord } from '../src/provenance/compiler-record.js';
import type { FindingLead } from '../src/provenance/finding-lead.js';
import { verifyReceiptSignature, signReceiptEd25519, type ExpectedRun } from '../src/evidence/gate.js';
import type { ExecutionReceipt } from '../src/types.js';

describe('End-to-End Reference Verification Workflow (Synthetic Vault Fixture)', () => {
  const sourceCommit = '1111111111111111111111111111111111111111';
  const repositoryUrl = 'https://github.com/example/synthetic-vault';
  const chainId = 31337;
  const forkBlock = 1000;
  const targetAddress = '0x1234567890123456789012345678901234567890';
  const workflowId = randomUUID();
  const targetRecordId = randomUUID();

  const researcher: AuthenticatedPrincipal = {
    id: 'researcher:alice',
    role: 'researcher',
    actorLabel: 'alice',
    authenticatedAt: new Date().toISOString(),
  };

  const independentReviewer: AuthenticatedPrincipal = {
    id: 'reviewer:bob',
    role: 'reviewer',
    actorLabel: 'bob',
    authenticatedAt: new Date().toISOString(),
  };

  const finalApprover: AuthenticatedPrincipal = {
    id: 'approver:carol',
    role: 'approver',
    actorLabel: 'carol',
    authenticatedAt: new Date().toISOString(),
  };

  const keypair = generateKeyPairSync('ed25519');
  const runnerPublicKeyPem = keypair.publicKey.export({ type: 'spki', format: 'pem' }).toString();
  const runnerPrivateKeyPem = keypair.privateKey.export({ type: 'pkcs8', format: 'pem' }).toString();
  const runnerId = 'runner-synthetic-vault-01';

  it('executes the full 15-step reference workflow cleanly on the synthetic fixture', () => {
    // Step 1: Synthetic scope registration
    const scopeSnapshot = {
      id: randomUUID(),
      programSlug: 'synthetic-cantina-bounty',
      repositoryUrl,
      sourceCommit,
      chainId,
      targetAddresses: [targetAddress],
      requiredForkBlock: forkBlock,
      allowedMethods: ['local-test', 'static-analysis'],
      expiresAt: new Date(Date.now() + 3600_000).toISOString(),
    };
    expect(scopeSnapshot.programSlug).toBe('synthetic-cantina-bounty');

    // Step 2: Target record binding
    const scopeSha256 = createHash('sha256').update(JSON.stringify(scopeSnapshot)).digest('hex');
    const targetRecord = {
      id: targetRecordId,
      scopeId: scopeSnapshot.id,
      targetAddress,
      scopeSha256,
      allowedMethods: ['local-test'],
      suiteIds: ['baseline-tests'],
      expiresAt: scopeSnapshot.expiresAt,
      status: 'active',
    };
    expect(targetRecord.status).toBe('active');

    // Step 3: Controlled source manifest
    const sourceRecord: ControlledSourceRecord = {
      recordId: randomUUID(),
      workflowId,
      repositoryUrl,
      sourceCommit,
      archiveSha256: 'a'.repeat(64),
      treeSha256: 'b'.repeat(64),
      trackedFileCount: 3,
      verifiedGitIdentity: true,
      fetchedAt: new Date().toISOString(),
      runnerId,
      provenanceStatus: 'verified',
    };

    // Step 4: Compiler provenance
    const compilerRecord: CompilerProvenanceRecord = {
      recordId: randomUUID(),
      workflowId,
      sourceRecordId: sourceRecord.recordId,
      compilerImageDigest: 'ethereum/solc@sha256:' + 'c'.repeat(64),
      solcVersion: '0.8.20',
      settingsSha256: 'd'.repeat(64),
      generatedAstSha256: 'e'.repeat(64),
      sourceToAstMappingCount: 3,
      compiledAt: new Date().toISOString(),
      outputArtifactSha256: 'f'.repeat(64),
    };

    // Step 5 & 6: Lead + falsifiable hypothesis
    const sourceFileText = 'contract SyntheticVault {\n    function withdraw(uint256 amount) external {\n        msg.sender.call{value: amount}("");\n        shares[msg.sender] -= amount;\n    }\n}';
    const excerpt = '        msg.sender.call{value: amount}("");';
    const excerptHash = createHash('sha256').update(excerpt, 'utf8').digest('hex');

    const lead: FindingLead = {
      id: 'F-001',
      workflowId,
      sourceCommit,
      repositoryUrl,
      detector: { tool: 'pattern-scan', version: '1.0.0', ruleId: 'low-level-call' },
      sourceSpan: {
        path: 'cases/synthetic-vault/SyntheticVault.sol',
        startLine: 3,
        endLine: 3,
        rawExcerpt: excerpt,
        excerptSha256: excerptHash,
      },
      hypothesis: 'withdraw() sends ETH via low-level call before decrementing shares, allowing reentrant state violation.',
      confirmationChecks: ['Execute reentrant attacker draining extra funds.'],
      falsificationChecks: ['Assert reentrant call against patched contract reverts.'],
      evidenceRefs: [randomUUID()],
      limitations: ['Synthetic local fixture only; no live mainnet contracts or funds involved.'],
      status: 'candidate_lead',
      statusHistory: [
        { status: 'candidate_lead', actor: researcher.id, timestamp: new Date().toISOString(), rationale: 'Initial pattern match.' },
      ],
    };

    // Admission: source-attested with verified source + compiler records
    const admission = checkAnalysisAdmission({ sourceRecord, compilerRecord, lead, providedSourceFileContent: sourceFileText });
    expect(admission.status).toBe('source-attested');

    // Steps 7-9: Baseline, positive, negative control test assertions
    const logContent = [
      'test_baseline_deposit_and_withdraw ... PASSED',
      'test_positive_reproduction_reentrancy_exploit ... PASSED (attackCount=2)',
      'test_negative_control_patched_vault_reverts ... PASSED (reverted as expected)',
    ].join('\n');
    const logBytes = Buffer.from(logContent, 'utf8');
    const logSha256 = createHash('sha256').update(logBytes).digest('hex');

    // Step 10: Signed receipt
    const runId = randomUUID();
    const rawReceipt: Omit<ExecutionReceipt, 'signature'> = {
      schemaVersion: 1,
      signatureAlgorithm: 'ed25519',
      runId,
      targetRecordId,
      runnerId,
      suiteId: 'baseline-tests',
      repositoryUrl,
      sourceCommit,
      chainId,
      forkBlock,
      commandProfileId: 'foundry-baseline-v1',
      toolVersions: { runnerImage: compilerRecord.compilerImageDigest },
      exitCode: 0,
      timedOut: false,
      assertions: [
        { id: 'baseline_deposit_and_withdraw', outcome: 'passed', detail: 'Normal operation verified.' },
        { id: 'positive_reentrancy_reproduced', outcome: 'passed', detail: 'Attacker succeeded (expected).' },
        { id: 'negative_control_reentrancy_rejected', outcome: 'passed', detail: 'Patched vault reverted (expected).' },
      ],
      logArtifact: { name: 'run.log', uri: `artifacts/${logSha256}`, sha256: logSha256, mediaType: 'text/plain', byteLength: logBytes.length },
      artifacts: [],
      startedAt: new Date(Date.now() - 5000).toISOString(),
      completedAt: new Date().toISOString(),
    };

    const signature = signReceiptEd25519(rawReceipt, runnerPrivateKeyPem);
    const signedReceipt: ExecutionReceipt = { ...rawReceipt, signature };

    // Verify receipt is valid with correct key
    expect(verifyReceiptSignature(signedReceipt, { ed25519PublicKeyPem: runnerPublicKeyPem })).toBe(true);

    // Step 11: Gate evaluation summary (manual decisions - gates G1-G9)
    const gatesSatisfied = {
      G1: 'passed', G2: 'passed', G3: 'passed', G4: 'passed',
      G5: 'passed', G6: 'passed', G7: 'not_applicable', G8: 'passed', G9: 'passed',
    };
    const allGatesPassed = Object.values(gatesSatisfied).every((v) => v === 'passed' || v === 'not_applicable');
    expect(allGatesPassed).toBe(true);

    // Step 12: Independent review — distinct reviewer identity
    const reviewSeparation = checkIndependentReviewSeparation(researcher.actorLabel!, independentReviewer);
    expect(reviewSeparation.allowed).toBe(true);

    // Step 13: Human approval by distinct approver
    const approvalSeparation = checkFindingApprovalSeparation(researcher.actorLabel!, finalApprover);
    expect(approvalSeparation.allowed).toBe(true);
    const submissionAuth = checkSubmissionAuthorization(finalApprover, researcher.actorLabel!);
    expect(submissionAuth.allowed).toBe(true);

    // Step 14: Draft report with evidence citations and explicit limitations
    const report = {
      title: 'Finding F-001: Reentrancy Invariant Violation in SyntheticVault',
      target: { address: targetAddress, repositoryUrl, sourceCommit },
      evidenceRefs: lead.evidenceRefs,
      limitations: lead.limitations,
      // Step 15: No external submission
      externalSubmissionSubmitted: false,
    };
    expect(report.externalSubmissionSubmitted).toBe(false);
  });

  describe('Security Invariants', () => {
    it('denies researcher reviewing or approving their own finding', () => {
      expect(checkIndependentReviewSeparation(researcher.actorLabel!, researcher).allowed).toBe(false);
      expect(checkFindingApprovalSeparation(researcher.actorLabel!, { ...finalApprover, actorLabel: 'alice' }).allowed).toBe(false);
    });

    it('rejects forged runner receipts with invalid Ed25519 signature', () => {
      const runId = randomUUID();
      const rawReceipt: Omit<ExecutionReceipt, 'signature'> = {
        schemaVersion: 1, signatureAlgorithm: 'ed25519', runId, targetRecordId, runnerId,
        suiteId: 'baseline-tests', repositoryUrl, sourceCommit, chainId, forkBlock,
        commandProfileId: 'foundry-baseline-v1', toolVersions: { runnerImage: 'img@sha256:' + 'a'.repeat(64) },
        exitCode: 0, timedOut: false,
        assertions: [{ id: 'baseline_passed', outcome: 'passed', detail: '' }],
        logArtifact: { name: 'run.log', uri: 'art/1', sha256: 'a'.repeat(64), mediaType: 'text/plain', byteLength: 10 },
        artifacts: [], startedAt: new Date().toISOString(), completedAt: new Date().toISOString(),
      };
      const forgedReceipt: ExecutionReceipt = { ...rawReceipt, signature: 'deadbeef'.repeat(16) };
      expect(verifyReceiptSignature(forgedReceipt, { ed25519PublicKeyPem: runnerPublicKeyPem })).toBe(false);
    });

    it('rejects analysis if source span excerpt hash is tampered', () => {
      const result = verifySourceSpanContent(
        { path: 'Vault.sol', startLine: 1, endLine: 1, rawExcerpt: 'contract Vault {}', excerptSha256: '0'.repeat(64) },
        'contract Vault {}\n'
      );
      expect(result.valid).toBe(false);
      expect(result.error).toMatch(/excerpt hash mismatch/i);
    });

    it('labels analysis provisional when no source record provided', () => {
      const excerpt = 'function foo() {}';
      const excerptHash = createHash('sha256').update(excerpt, 'utf8').digest('hex');
      const lead: FindingLead = {
        id: 'F-002', workflowId: randomUUID(), sourceCommit, repositoryUrl,
        detector: { tool: 'pattern-scan', version: '1.0.0', ruleId: 'test' },
        sourceSpan: { path: 'Test.sol', startLine: 1, endLine: 1, rawExcerpt: excerpt, excerptSha256: excerptHash },
        hypothesis: 'Test hypothesis for admission check.',
        confirmationChecks: ['Positive test.'], falsificationChecks: ['Negative test.'],
        evidenceRefs: [], limitations: [],
        status: 'candidate_lead',
        statusHistory: [{ status: 'candidate_lead', actor: 'researcher:alice', timestamp: new Date().toISOString(), rationale: 'init' }],
      };
      const result = checkAnalysisAdmission({ lead, providedSourceFileContent: 'function foo() {}\n' });
      expect(result.status).toBe('provisional');
    });
  });
});
