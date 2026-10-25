import { classifyTask, decideRoute, OperationsAuditLog, type RequestEnvelope } from "./index.ts";
const request: RequestEnvelope = { requestId: "demo-1", tenantId: "tenant-demo", userId: "user-demo", sessionId: "session-demo", task: "Research public documentation", requestedAction: "find information", dataSensitivity: "public", requestedTools: ["docs-search"], risk: "low", contextRefs: [] };
const classification = classifyTask(request.task, request.requestedAction);
const decision = decideRoute(request, classification, { approvedTools: ["docs-search"], writeTools: [] });
const audit = new OperationsAuditLog();
audit.append({ requestId: request.requestId, tenantId: request.tenantId, actor: request.userId, event: "route.decided", details: { category: classification.taskCategory, mode: decision.mode } });
console.log(JSON.stringify({ classification, decision, auditFingerprint: audit.fingerprint(request.tenantId) }, null, 2));
