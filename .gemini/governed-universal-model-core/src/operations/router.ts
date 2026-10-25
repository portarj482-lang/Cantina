import type { Classification, PolicyContext, RequestEnvelope, RouteDecision } from "./types.ts";

const POLICY_VERSION = "ops-policy-0.1.0";
const validId = (value: string): boolean => typeof value === "string" && value.trim().length > 0;

/** Fail-closed route policy. This plans a route; it does not execute tools. */
export function decideRoute(request: RequestEnvelope, classification: Classification, policy: PolicyContext): RouteDecision {
  const reasons: string[] = [];
  let mode: RouteDecision["mode"] = "answer-only";
  const allowedTools: string[] = [];
  const invalid = [request.requestId, request.tenantId, request.userId, request.sessionId, request.task, request.requestedAction]
    .some(value => !validId(value));
  if (invalid) reasons.push("Required request identity or task fields are missing.");
  if (policy.tenantBlocked) reasons.push("Tenant is blocked by policy.");
  if (policy.deniedUsers?.includes(request.userId)) reasons.push("User is denied by policy.");
  if (request.dataSensitivity === "unknown") reasons.push("Data sensitivity is unknown.");
  if (request.risk === "critical") reasons.push("Critical-risk requests require explicit human authorization.");
  if (classification.taskCategory === "unknown" || classification.confidence < 0.5) reasons.push("Task classification is unknown or low confidence.");

  const denied = reasons.length > 0;
  if (denied) mode = "deny";
  else if (request.risk === "high" || request.risk === "critical" || classification.needsHumanReview || (policy.requireHumanForSensitiveData && ["confidential", "sensitive"].includes(request.dataSensitivity))) {
    mode = "human-gated";
    reasons.push("Independent human authorization is required before execution.");
  } else if (request.requestedTools.length > 0) {
    const requested = [...new Set(request.requestedTools)];
    const unapproved = requested.filter(tool => !policy.approvedTools.includes(tool));
    if (unapproved.length) {
      mode = "deny";
      reasons.push(`Unapproved tool(s) requested: ${unapproved.join(", ")}.`);
    } else {
      const writes = requested.filter(tool => policy.writeTools.includes(tool));
      if (writes.length) {
        mode = "human-gated";
        reasons.push(`Write-capable tool(s) require human authorization: ${writes.join(", ")}.`);
      } else {
        mode = "read-tool";
        allowedTools.push(...requested);
        reasons.push("Only explicitly approved read tools are eligible for routing.");
      }
    }
  } else {
    reasons.push("No external tool requested; answer-only route selected.");
  }
  if (mode !== "read-tool") allowedTools.length = 0;
  return { requestId: request.requestId, tenantId: request.tenantId, userId: request.userId, mode, allowedTools, reasons, policyVersion: POLICY_VERSION, decidedAt: new Date().toISOString() };
}
