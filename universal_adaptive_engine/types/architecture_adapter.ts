/**
 * TypeScript Architecture Adapter Interface.
 * Version: 1.0.0
 */

import { TaskRecord, EvidenceRecord } from "./canonical_schemas";

export interface DiscoveryResult {
  adapter: string;
  version: string;
  workspace_root: string;
  capabilities: Record<string, unknown>;
  evidence: EvidenceRecord[];
  [key: string]: unknown;
}

export interface ValidationResult {
  valid: boolean;
  task_id: string;
  issues: string[];
  recommendation: "PROCEED" | "REJECT_OR_ADAPT" | "REJECT_VIOLATION";
}

export interface AdapterExecutionResult {
  success: boolean;
  status: string;
  output?: unknown;
  evidence: EvidenceRecord[];
  errors: string[];
  timestamp: string;
}

export interface HealthCheckResult {
  adapter: string;
  status: "HEALTHY" | "DEGRADED" | "UNHEALTHY";
  timestamp: string;
  [key: string]: unknown;
}

/**
 * Host Architecture Adapter Interface.
 * Translates universal canonical requests into host-native actions.
 */
export interface ArchitectureAdapter {
  /**
   * Discover observed components, capabilities, constraints, and evidence.
   */
  discover(): Promise<DiscoveryResult>;

  /**
   * Validate a canonical request or task against host-native interfaces and safety boundaries.
   */
  validateContract(contract: Record<string, unknown>): Promise<ValidationResult>;
  validate_contract?(contract: Record<string, unknown>): Promise<ValidationResult>;

  /**
   * Execute only authorized work and return structured evidence.
   */
  execute(task: TaskRecord | Record<string, unknown>): Promise<AdapterExecutionResult>;

  /**
   * Report adapter availability and health without hiding failures.
   */
  healthCheck(): Promise<HealthCheckResult>;
  health_check?(): Promise<HealthCheckResult>;
}
