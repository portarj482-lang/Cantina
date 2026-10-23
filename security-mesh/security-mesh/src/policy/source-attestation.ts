export interface SourceAttestationRecord {
  evidence_kind: string;
  metadata: unknown;
}

export interface SourceAttestationCheck {
  ok: boolean;
  reason: string;
}

function normalizeRepository(url: string): string {
  return url.trim().replace(/\/+$/, '').replace(/\.git$/i, '').toLowerCase();
}

function isSafeSourcePath(path: string): boolean {
  if (!path || path.includes('\\') || path.startsWith('/') || path.includes('\0')) return false;
  const segments = path.split('/');
  if (segments.some((segment) => !segment || segment === '.' || segment === '..')) return false;
  return !/^[a-zA-Z]:/.test(path);
}

function isValidLineReference(value: unknown): boolean {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return false;
  const item = value as Record<string, unknown>;
  return typeof item.path === 'string'
    && isSafeSourcePath(item.path)
    && typeof item.startLine === 'number'
    && Number.isSafeInteger(item.startLine) && item.startLine > 0
    && typeof item.endLine === 'number'
    && Number.isSafeInteger(item.endLine) && item.endLine >= item.startLine
    && typeof item.excerptSha256 === 'string'
    && /^[a-fA-F0-9]{64}$/.test(item.excerptSha256);
}

/**
 * Checks that human-verified evidence contains a source attestation bound to the
 * workflow's exact repository and commit. This validates recorded evidence shape;
 * it does not independently authenticate Git hosting or replace human artifact review.
 */
export function validateSourceAttestationEvidence(
  records: SourceAttestationRecord[],
  expectedRepositoryUrl: string,
  expectedCommitSha: string,
): SourceAttestationCheck {
  if (!records.some((record) => record.evidence_kind === 'source-manifest')) {
    return { ok: false, reason: 'Verified source-manifest evidence is required.' };
  }

  const expectedRepo = normalizeRepository(expectedRepositoryUrl);
  const expectedCommit = expectedCommitSha.toLowerCase();
  const validAttestation = records.some((record) => {
    if (record.evidence_kind !== 'source-attestation' || !record.metadata || typeof record.metadata !== 'object' || Array.isArray(record.metadata)) return false;
    const metadata = record.metadata as Record<string, unknown>;
    const lineRefs = metadata.sourceLineRefs;
    const hasValidLineRefs = Array.isArray(lineRefs) && lineRefs.length > 0 && lineRefs.every(isValidLineReference);
    return typeof metadata.repositoryUrl === 'string'
      && normalizeRepository(metadata.repositoryUrl) === expectedRepo
      && typeof metadata.commitSha === 'string'
      && metadata.commitSha.toLowerCase() === expectedCommit
      && metadata.repositoryIdentityVerified === true
      && metadata.commitObjectVerified === true
      && metadata.lineProvenanceVerified === true
      && hasValidLineRefs;
  });

  return validAttestation
    ? { ok: true, reason: 'Verified source attestation matches the workflow repository, commit, and source-line references.' }
    : { ok: false, reason: 'A verified source-attestation record bound to the exact repository and commit, with valid source-line references, is required.' };
}
