import type { TargetRecordBinding, OracleDecision } from './target-record.js';
import type { WorkflowCreateInput } from '../schemas.js';

export function authorizeTargetDispatch(
  targetRecord: TargetRecordBinding | undefined,
  request: WorkflowCreateInput,
  now = new Date(),
): OracleDecision {
  const reasons: string[] = [];
  if (!targetRecord) reasons.push('No validated target record is bound to this dispatch.');
  else {
    if (targetRecord.disabledAt) reasons.push('Target record has been revoked.');
    if (targetRecord.id !== request.targetRecordId) reasons.push('Dispatch target record ID mismatch.');
    if (!targetRecord.expiresAt || !Number.isFinite(Date.parse(targetRecord.expiresAt)) || Date.parse(targetRecord.expiresAt) <= now.getTime()) reasons.push('Target record expired before dispatch.');
    if (request.programSlug !== targetRecord.programSlug) reasons.push('Dispatch program does not match target record.');
    if (!request.repositoryUrl || !targetRecord.repositoryUrl || request.repositoryUrl.replace(/\/+$/, '').replace(/\.git$/i, '').toLowerCase() !== targetRecord.repositoryUrl.replace(/\/+$/, '').replace(/\.git$/i, '').toLowerCase()) reasons.push('Dispatch repository does not match target record.');
    if (!request.sourceCommit || !targetRecord.sourceCommit || request.sourceCommit.toLowerCase() !== targetRecord.sourceCommit.toLowerCase()) reasons.push('Dispatch source commit does not match target record.');
    if (request.chainId !== targetRecord.chainId || request.forkBlock !== targetRecord.forkBlock) reasons.push('Dispatch chain or block pin does not match target record.');
    if (!Array.isArray(request.targetAddresses) || request.targetAddresses.length !== 1 || !targetRecord.targetAddress || request.targetAddresses[0]?.toLowerCase() !== targetRecord.targetAddress.toLowerCase()) reasons.push('Dispatch must use only the target record address.');
    if (!Array.isArray(targetRecord.allowedMethods) || request.requestedMethods.some((method) => !targetRecord.allowedMethods.includes(method))) reasons.push('Dispatch requests a method not granted by the target record.');
  }
  return { oracleId: 'target-dispatch-oracle', outcome: reasons.length ? 'deny' : 'allow', reasons, ...(targetRecord ? { bindingSha256: targetRecord.scopeSha256 } : {}) };
}
