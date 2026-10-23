import { describe, expect, it } from 'vitest';
import { randomUUID, createHash } from 'node:crypto';
import { validateSourceRecord, type ControlledSourceRecord } from '../src/provenance/source-record.js';
import { validateCompilerRecord, type CompilerProvenanceRecord } from '../src/provenance/compiler-record.js';
import { validateFindingLead, type FindingLead } from '../src/provenance/finding-lead.js';
import { checkAnalysisAdmission, verifySourceSpanContent } from '../src/provenance/admission.js';

describe('Controlled Source Acquisition and Compiler Provenance', () => {
  const commit = 'a'.repeat(40);
  const repo = 'https://github.com/example/safe-protocol';
  const sampleFileContent = 'contract Vault {\n    function deposit() external {}\n    function withdraw() external {}\n}\n';
  const sampleExcerpt = '    function deposit() external {}';
  const sampleExcerptHash = createHash('sha256').update(sampleExcerpt, 'utf8').digest('hex');

  const validSourceRecord: ControlledSourceRecord = {
    recordId: randomUUID(),
    workflowId: randomUUID(),
    repositoryUrl: repo,
    sourceCommit: commit,
    archiveSha256: 'b'.repeat(64),
    treeSha256: 'c'.repeat(64),
    trackedFileCount: 12,
    verifiedGitIdentity: true,
    fetchedAt: new Date().toISOString(),
    runnerId: 'runner-01',
    provenanceStatus: 'verified',
  };

  const validCompilerRecord: CompilerProvenanceRecord = {
    recordId: randomUUID(),
    workflowId: validSourceRecord.workflowId,
    sourceRecordId: validSourceRecord.recordId,
    compilerImageDigest: 'ethereum/solc@sha256:' + 'd'.repeat(64),
    solcVersion: '0.8.24',
    settingsSha256: 'e'.repeat(64),
    generatedAstSha256: 'f'.repeat(64),
    sourceToAstMappingCount: 5,
    compiledAt: new Date().toISOString(),
    outputArtifactSha256: '1'.repeat(64),
  };

  const validLead: FindingLead = {
    id: 'F-001',
    workflowId: validSourceRecord.workflowId,
    sourceCommit: commit,
    repositoryUrl: repo,
    detector: {
      tool: 'slither',
      version: '0.10.1',
      ruleId: 'reentrancy-no-eth',
    },
    sourceSpan: {
      path: 'contracts/Vault.sol',
      startLine: 2,
      endLine: 2,
      rawExcerpt: sampleExcerpt,
      excerptSha256: sampleExcerptHash,
    },
    hypothesis: 'Potential state update ordering issue in deposit function.',
    confirmationChecks: ['Execute positive test case with reentrant caller.'],
    falsificationChecks: ['Assert reentrancy guard reverts call.'],
    evidenceRefs: [randomUUID()],
    limitations: ['Local unit test only; does not simulate external pool state.'],
    status: 'candidate_lead',
    statusHistory: [
      {
        status: 'candidate_lead',
        actor: 'researcher:alice',
        timestamp: new Date().toISOString(),
        rationale: 'Initial detector output from pattern scan.',
      },
    ],
  };

  it('validates a compliant controlled source record', () => {
    const result = validateSourceRecord(validSourceRecord);
    expect(result.success).toBe(true);
  });

  it('rejects source records from unapproved hosts or invalid commit SHAs', () => {
    const invalidRepo = { ...validSourceRecord, repositoryUrl: 'https://evil-unapproved-host.xyz/repo' };
    expect(validateSourceRecord(invalidRepo).success).toBe(false);

    const invalidCommit = { ...validSourceRecord, sourceCommit: 'short-sha' };
    expect(validateSourceRecord(invalidCommit).success).toBe(false);
  });

  it('validates a compliant compiler provenance record with pinned digest', () => {
    const result = validateCompilerRecord(validCompilerRecord);
    expect(result.success).toBe(true);
  });

  it('rejects compiler records without pinned sha256 image digest', () => {
    const unpinnedImage = { ...validCompilerRecord, compilerImageDigest: 'ethereum/solc:latest' };
    expect(validateCompilerRecord(unpinnedImage).success).toBe(false);
  });

  it('validates source span content against actual file content and detects tampering', () => {
    const validSpanCheck = verifySourceSpanContent(validLead.sourceSpan, sampleFileContent);
    expect(validSpanCheck.valid).toBe(true);

    const tamperedSpan = { ...validLead.sourceSpan, excerptSha256: '0'.repeat(64) };
    const invalidSpanCheck = verifySourceSpanContent(tamperedSpan, sampleFileContent);
    expect(invalidSpanCheck.valid).toBe(false);
    expect(invalidSpanCheck.error).toMatch(/excerpt hash mismatch/i);
  });

  it('admits analysis as source-attested when backed by verified source and compiler records', () => {
    const admission = checkAnalysisAdmission({
      sourceRecord: validSourceRecord,
      compilerRecord: validCompilerRecord,
      lead: validLead,
      providedSourceFileContent: sampleFileContent,
    });
    expect(admission.status).toBe('source-attested');
  });

  it('labels caller-supplied analysis as provisional when source records are missing', () => {
    const admission = checkAnalysisAdmission({
      lead: validLead,
      providedSourceFileContent: sampleFileContent,
    });
    expect(admission.status).toBe('provisional');
    expect(admission.reasons.some((r) => r.includes('provisional'))).toBe(true);
  });

  it('rejects analysis if commit or repository in lead contradicts source record', () => {
    const mismatchedLead = { ...validLead, sourceCommit: '0'.repeat(40) };
    const admission = checkAnalysisAdmission({
      sourceRecord: validSourceRecord,
      compilerRecord: validCompilerRecord,
      lead: mismatchedLead,
      providedSourceFileContent: sampleFileContent,
    });
    expect(admission.status).toBe('rejected');
    expect(admission.reasons[0]).toMatch(/Source commit mismatch/i);
  });
});
