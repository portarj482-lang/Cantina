/**
 * Canonical Schema Type Definitions for Universal Adaptive Intelligence Architecture.
 * Version: 1.0.0
 */

export enum TaskState {
  PROPOSED = "PROPOSED",
  READY = "READY",
  RUNNING = "RUNNING",
  WAITING = "WAITING",
  BLOCKED = "BLOCKED",
  FAILED = "FAILED",
  CANCELLED = "CANCELLED",
  VERIFYING = "VERIFYING",
  COMPLETED_WITH_LIMITATIONS = "COMPLETED_WITH_LIMITATIONS",
  COMPLETED_VERIFIED = "COMPLETED_VERIFIED",
}

export enum RiskLevel {
  LOW = "low",
  MEDIUM = "medium",
  HIGH = "high",
  CRITICAL = "critical",
}

export enum FindingStatus {
  CANDIDATE = "CANDIDATE",
  SUPPORTED = "SUPPORTED",
  REFUTED = "REFUTED",
  UNRESOLVED = "UNRESOLVED",
  ACCEPTED = "ACCEPTED",
  DUPLICATE = "DUPLICATE",
  REJECTED = "REJECTED",
}

export enum ImpactLevel {
  CRITICAL = "critical",
  HIGH = "high",
  MEDIUM = "medium",
  LOW = "low",
  INFORMATIONAL = "informational",
  UNKNOWN = "unknown",
}

export enum ExploitabilityLevel {
  DEMONSTRATED = "demonstrated",
  PLAUSIBLE = "plausible",
  THEORETICAL = "theoretical",
  UNVERIFIED = "unverified",
  REFUTED = "refuted",
}

export enum ConfidenceLevel {
  VERIFIED = "verified",
  HIGH = "high",
  MEDIUM = "medium",
  LOW = "low",
  UNVERIFIED = "unverified",
  REFUTED = "refuted",
}

export enum CandidateType {
  SKILL = "skill",
  AGENT = "agent",
  TOOL = "tool",
  DATASET = "dataset",
  PROMPT = "prompt",
  SERVICE = "service",
  PATTERN = "pattern",
  ADAPTER = "adapter",
}

export enum AdaptationDecision {
  ACCEPTED_FOR_STAGING = "ACCEPTED_FOR_STAGING",
  ACCEPTED_FOR_PRODUCTION = "ACCEPTED_FOR_PRODUCTION",
  NEEDS_ADAPTATION = "NEEDS_ADAPTATION",
  NEEDS_REVIEW = "NEEDS_REVIEW",
  QUARANTINED = "QUARANTINED",
  REJECTED = "REJECTED",
  DEPRECATED = "DEPRECATED",
  ROLLED_BACK = "ROLLED_BACK",
}

export enum EvidenceType {
  OBSERVED = "OBSERVED",
  DERIVED = "DERIVED",
  HYPOTHESIS = "HYPOTHESIS",
  UNVERIFIED = "UNVERIFIED",
  REFUTED = "REFUTED",
  SUPERSEDED = "SUPERSEDED",
}

export enum BlockerCategory {
  MISSING_CONTEXT = "MISSING_CONTEXT",
  INVALID_INPUT = "INVALID_INPUT",
  TOOL_UNAVAILABLE = "TOOL_UNAVAILABLE",
  PERMISSION_DENIED = "PERMISSION_DENIED",
  POLICY_BLOCK = "POLICY_BLOCK",
  DEPENDENCY_FAILURE = "DEPENDENCY_FAILURE",
  RESOURCE_LIMIT = "RESOURCE_LIMIT",
  ENVIRONMENT_FAILURE = "ENVIRONMENT_FAILURE",
  TEST_FAILURE = "TEST_FAILURE",
  UNKNOWN = "UNKNOWN",
}

export enum CapabilityStatus {
  VERIFIED = "VERIFIED",
  PARTIAL = "PARTIAL",
  ASSUMED = "ASSUMED",
  BLOCKED = "BLOCKED",
  FAILED = "FAILED",
  UNKNOWN = "UNKNOWN",
}

export interface TaskBlocker {
  category: BlockerCategory;
  message: string;
  recoverable: boolean;
  diagnosis?: string;
  recovery_action?: string;
  stop_condition?: string;
}

export interface TaskTests {
  passed: unknown[];
  failed: unknown[];
  skipped: unknown[];
  not_run: unknown[];
}

export interface TaskRecord {
  task_id: string;
  goal: string;
  status: TaskState;
  owner: string;
  assigned_role?: string | null;
  dependencies: string[];
  inputs?: unknown[];
  expected_artifacts: string[];
  acceptance_criteria: string[];
  permissions_required?: string[];
  risk_level: RiskLevel;
  attempt_count: number;
  evidence_refs: string[];
  blocker?: TaskBlocker | null;
  tests: TaskTests;
  limitations?: string[];
  next_action: string;
  created_at?: string;
  updated_at?: string;
}

export interface LocationRef {
  path: string;
  start_line?: number | null;
  end_line?: number | null;
  symbol?: string | null;
}

export interface RegressionResult {
  test_id: string;
  outcome: "passed" | "failed" | "skipped";
  details?: string;
}

export interface FindingRecord {
  finding_id: string;
  title: string;
  status: FindingStatus;
  source_refs: string[];
  affected_versions: string[];
  locations: LocationRef[];
  original_labels: string[];
  derived_labels: string[];
  preconditions: string[];
  security_property?: string | null;
  root_cause?: string | null;
  impact: ImpactLevel;
  exploitability: ExploitabilityLevel;
  reproduction_refs: string[];
  counterevidence_refs: string[];
  fix_refs: string[];
  regression_results: RegressionResult[];
  confidence: ConfidenceLevel;
  unresolved_assumptions: string[];
  created_at?: string;
  updated_at?: string;
}

export interface CompatibilityMatrix {
  contracts: "compatible" | "incompatible" | "not_checked" | "needs_adapter";
  dependencies: "compatible" | "incompatible" | "not_checked" | "missing_dependency";
  security: "passed" | "failed" | "not_checked" | "sandbox_required";
  regressions: "none_observed" | "degraded" | "not_checked";
}

export interface AdaptationRecord {
  candidate_id: string;
  candidate_type: CandidateType;
  license: string;
  intended_capability: string;
  rationale: string;
  compatibility: CompatibilityMatrix;
  source_ref?: string | null;
  version?: string | null;
  checksum?: string | null;
  baseline_ref?: string | null;
  candidate_evaluation_ref?: string | null;
  protected_core_changed: boolean;
  shared_contracts_changed: boolean;
  approval_required: boolean;
  approval_ref?: string | null;
  decision: AdaptationDecision;
  rollback_ref?: string | null;
  created_at?: string;
  updated_at?: string;
}

export interface EvidenceRecord {
  evidence_id: string;
  evidence_type: EvidenceType;
  source_ref: string;
  acquisition_method: string;
  observed_result: string;
  confidence: ConfidenceLevel;
  artifact_path?: string | null;
  sha256?: string | null;
  tool_version?: string | null;
  related_task_id?: string | null;
  limitations?: string[];
  timestamp?: string;
}

export interface CapabilityRecord {
  capability_id: string;
  display_name: string;
  status: CapabilityStatus;
  implementation_ref?: string | null;
  interface_ref?: string | null;
  owner?: string | null;
  permissions_required?: string[];
  inputs?: string[];
  outputs?: string[];
  dependencies?: string[];
  evidence_refs?: string[];
  limitations?: string[];
  last_verified_at?: string | null;
}

export enum WorkflowStage {
  INTAKE = "INTAKE",
  DISCOVERY = "DISCOVERY",
  BASELINE = "BASELINE",
  DECOMPOSITION = "DECOMPOSITION",
  PLAN = "PLAN",
  AUTHORIZATION_CHECK = "AUTHORIZATION_CHECK",
  IMPLEMENTATION = "IMPLEMENTATION",
  VERIFICATION = "VERIFICATION",
  INDEPENDENT_REVIEW = "INDEPENDENT_REVIEW",
  STAGING = "STAGING",
  APPROVAL = "APPROVAL",
  DEPLOYMENT = "DEPLOYMENT",
  POST_DEPLOYMENT_VALIDATION = "POST_DEPLOYMENT_VALIDATION",
  COMPLETION_REPORT = "COMPLETION_REPORT",
}

export interface CommandRunResult {
  command: string;
  exit_code: number;
  duration_ms?: number;
}

export interface HandoffRecord {
  task_id: string;
  agent_role: string;
  status: "COMPLETED_VERIFIED" | "COMPLETED_WITH_LIMITATIONS" | "BLOCKED" | "FAILED" | "NOT_RUN" | "IN_PROGRESS";
  summary: string;
  stage?: string | null;
  claims: string[];
  evidence_refs: string[];
  files_inspected: string[];
  files_changed: string[];
  commands_run: CommandRunResult[];
  tests: TaskTests;
  artifacts: string[];
  assumptions: string[];
  limitations: string[];
  security_concerns: string[];
  next_action: string;
  timestamp?: string;
}

export interface PipelineStageConfig {
  stage: WorkflowStage;
  workflow_agent_id: string;
  required: boolean;
  skippable: boolean;
  skip_reason?: string | null;
}

export interface PipelineExecutionReport {
  pipeline_name: string;
  goal: string;
  overall_status: string;
  stage_handoffs: Record<string, HandoffRecord>;
  evidence_collected: string[];
  limitations: string[];
  blockers: string[];
  timestamp?: string;
}

