export type BoundaryStatus = "captured" | "quarantined" | "verified" | "admitted" | "rejected";
export type BoundaryKind = "source" | "claim" | "hypothesis" | "decision" | "evidence" | "handoff";
export type FieldState<T> = { readonly state: "known"; readonly value: T } | { readonly state: "unknown"; readonly reason: string };

export interface BoundaryProvenance {
  readonly sourceType: string;
  readonly sourceLocator: string;
  readonly sourceRevision: FieldState<string>;
  readonly contentSha256: string;
  readonly capturedAt: string;
  readonly capturedBy: string;
}

export interface BoundaryRecord<T = unknown> {
  readonly id: string;
  readonly projectId: string;
  readonly kind: BoundaryKind;
  readonly payload: T;
  readonly provenance: BoundaryProvenance;
  readonly status: BoundaryStatus;
  readonly ambiguityReasons: readonly string[];
  readonly unknownFields: readonly string[];
  readonly evidenceIds: readonly string[];
  readonly createdAt: string;
  readonly updatedAt: string;
  readonly version: number;
}

export interface BoundaryAuditEvent {
  readonly id: string;
  readonly recordId: string;
  readonly projectId: string;
  readonly actor: string;
  readonly action: string;
  readonly fromStatus: BoundaryStatus | null;
  readonly toStatus: BoundaryStatus;
  readonly reason: string;
  readonly policyVersion: string;
  readonly evidenceIds: readonly string[];
  readonly occurredAt: string;
}

export interface CaptureBoundaryInput<T> {
  readonly id?: string;
  readonly projectId: string;
  readonly kind: BoundaryKind;
  readonly payload: T;
  readonly sourceType: string;
  readonly sourceLocator: string;
  readonly sourceRevision?: string;
  readonly capturedBy: string;
  readonly ambiguityReasons?: readonly string[];
  readonly unknownFields?: readonly string[];
  readonly evidenceIds?: readonly string[];
}

export interface AdmissionCheck {
  readonly name: string;
  readonly passed: boolean;
  readonly detail?: string;
}

export interface AdmissionRequest {
  readonly actor: string;
  readonly reviewer: string;
  readonly reason: string;
  readonly policyVersion: string;
  readonly evidenceIds: readonly string[];
  readonly checks: readonly AdmissionCheck[];
  readonly requiredChecks: readonly string[];
  readonly expectedSourceRevision: string;
}
