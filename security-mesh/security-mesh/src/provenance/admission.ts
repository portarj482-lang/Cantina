import type { ControlledSourceRecord } from './source-record.js';
import type { CompilerProvenanceRecord } from './compiler-record.js';
import type { FindingLead, SourceSpan } from './finding-lead.js';
import { createHash } from 'node:crypto';

export type AnalysisProvenanceStatus = 'source-attested' | 'provisional' | 'rejected';

export interface AdmissionCheckResult {
  status: AnalysisProvenanceStatus;
  reasons: string[];
}

/**
 * Validates whether an analysis lead can be admitted as verified source-attested,
 * remains marked provisional (e.g. caller-supplied AST/sources without runner checkout),
 * or is rejected (mismatches, missing hashes, or fabricated spans).
 */
export function checkAnalysisAdmission(params: {
  sourceRecord?: ControlledSourceRecord;
  compilerRecord?: CompilerProvenanceRecord;
  lead: FindingLead;
  providedSourceFileContent?: string;
}): AdmissionCheckResult {
  const reasons: string[] = [];
  const { sourceRecord, compilerRecord, lead, providedSourceFileContent } = params;

  // 1. Verify source commit match
  if (sourceRecord) {
    if (sourceRecord.sourceCommit.toLowerCase() !== lead.sourceCommit.toLowerCase()) {
      return {
        status: 'rejected',
        reasons: [`Source commit mismatch: source record has ${sourceRecord.sourceCommit}, lead cites ${lead.sourceCommit}.`],
      };
    }
    const normRecordRepo = sourceRecord.repositoryUrl.replace(/\/+$/, '').toLowerCase();
    const normLeadRepo = lead.repositoryUrl.replace(/\/+$/, '').toLowerCase();
    if (normRecordRepo !== normLeadRepo) {
      return {
        status: 'rejected',
        reasons: [`Repository URL mismatch: record has ${normRecordRepo}, lead cites ${normLeadRepo}.`],
      };
    }
  }

  // 2. Validate source span against actual content if available
  if (providedSourceFileContent) {
    const spanValidation = verifySourceSpanContent(lead.sourceSpan, providedSourceFileContent);
    if (!spanValidation.valid) {
      return {
        status: 'rejected',
        reasons: [`Source span validation failed: ${spanValidation.error}`],
      };
    }
  } else if (!sourceRecord) {
    // Missing source record and missing source content -> cannot verify span
    reasons.push('No controlled source record or source text available; source provenance cannot be attested.');
  }

  // 3. Check compiler provenance
  if (compilerRecord) {
    if (sourceRecord && compilerRecord.sourceRecordId !== sourceRecord.recordId) {
      return {
        status: 'rejected',
        reasons: ['Compiler provenance record is not bound to the controlled source record.'],
      };
    }
  }

  // 4. Determine final admission status
  if (sourceRecord && sourceRecord.provenanceStatus === 'verified' && compilerRecord) {
    return {
      status: 'source-attested',
      reasons: ['Verified controlled source checkout and deterministic compiler provenance established.'],
    };
  }

  return {
    status: 'provisional',
    reasons: [
      'Caller-supplied or unverified source/compile data; results remain marked provisional until controlled runner attestation is established.',
      ...reasons,
    ],
  };
}

export function verifySourceSpanContent(
  span: SourceSpan,
  fileContent: string
): { valid: boolean; error?: string } {
  const lines = fileContent.split('\n');
  if (span.startLine < 1 || span.endLine > lines.length || span.startLine > span.endLine) {
    return {
      valid: false,
      error: `Span lines [${span.startLine}-${span.endLine}] are out of range for file with ${lines.length} lines.`,
    };
  }

  const excerptLines = lines.slice(span.startLine - 1, span.endLine);
  const actualExcerpt = excerptLines.join('\n');
  const actualHash = createHash('sha256').update(actualExcerpt, 'utf8').digest('hex');

  if (actualHash.toLowerCase() !== span.excerptSha256.toLowerCase()) {
    return {
      valid: false,
      error: `Source excerpt hash mismatch: computed ${actualHash}, declared ${span.excerptSha256}.`,
    };
  }

  return { valid: true };
}
