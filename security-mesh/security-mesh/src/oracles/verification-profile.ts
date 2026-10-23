import { getSuite } from '../tools/registry.js';
import type { TargetRecordBinding, OracleDecision } from './target-record.js';

export function selectVerificationProfile(target: TargetRecordBinding, suiteId: string, now = new Date()): OracleDecision {
  const suite = getSuite(suiteId);
  const reasons: string[] = [];
  if (target.disabledAt) reasons.push('Target record has been revoked.');
  if (!target.expiresAt || !Number.isFinite(Date.parse(target.expiresAt)) || Date.parse(target.expiresAt) <= now.getTime()) reasons.push('Target record is expired or has an invalid expiry.');
  if (!Array.isArray(target.suiteIds) || !target.suiteIds.includes(suiteId)) reasons.push('Suite is not allowlisted for this target record.');
  if (!suite || !suite.dispatchEnabled) reasons.push('Suite has no enabled fixed runner profile.');
  else if (!Array.isArray(target.allowedMethods) || !target.allowedMethods.includes(suite.requiredMethod)) reasons.push('Suite method is not authorized for this target.');
  if (reasons.length) return { oracleId: 'verification-profile-oracle', outcome: 'deny', reasons, bindingSha256: target.scopeSha256 };
  return { oracleId: 'verification-profile-oracle', outcome: 'allow', reasons: [], bindingSha256: target.scopeSha256 };
}
