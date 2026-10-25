export type TaskCategory = "writing" | "coding" | "research" | "analysis" | "planning" | "classification" | "external-action" | "unknown";
export type DataSensitivity = "public" | "internal" | "confidential" | "sensitive" | "unknown";
export type ExecutionMode = "answer-only" | "read-tool" | "write-tool" | "human-gated" | "deny";
export type RiskLevel = "low" | "moderate" | "high" | "critical";

export interface RequestEnvelope {
  requestId: string;
  tenantId: string;
  userId: string;
  sessionId: string;
  task: string;
  requestedAction: string;
  dataSensitivity: DataSensitivity;
  requestedTools: string[];
  risk: RiskLevel;
  contextRefs: string[];
}
export interface Classification {
  taskCategory: TaskCategory;
  confidence: number;
  rationale: string[];
  needsHumanReview: boolean;
}
export interface PolicyContext {
  approvedTools: string[];
  writeTools: string[];
  deniedUsers?: string[];
  tenantBlocked?: boolean;
  requireHumanForSensitiveData?: boolean;
}
export interface RouteDecision {
  requestId: string;
  tenantId: string;
  userId: string;
  mode: ExecutionMode;
  allowedTools: string[];
  reasons: string[];
  policyVersion: string;
  decidedAt: string;
}
export interface AuditRecord {
  sequence: number;
  timestamp: string;
  requestId: string;
  tenantId: string;
  actor: string;
  event: string;
  details: Record<string, unknown>;
}
