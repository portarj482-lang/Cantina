export type RightsBasis = "creator-assertion" | "written-license" | "employment-assignment" | "third-party-license" | "public-domain" | "unknown";
export type RightsStatus = "unreviewed" | "documented" | "approved-for-use" | "restricted" | "disputed";
export type ConsentScope = "internal-development" | "commercial-use" | "model-training" | "redistribution" | "publication";
export interface RightsAsset {
  assetId: string;
  title: string;
  creator: string;
  createdAt: string;
  description: string;
  provenanceRefs: string[];
  basis: RightsBasis;
  status: RightsStatus;
  permittedScopes: ConsentScope[];
  excludedScopes: ConsentScope[];
  evidenceRefs: string[];
  reviewer?: string;
  notes: string[];
}
export interface LicenseGrant {
  grantId: string;
  assetId: string;
  licensor: string;
  licensee: string;
  scope: ConsentScope[];
  startDate: string;
  endDate?: string;
  revocable: boolean;
  consideration: string;
  signedDocumentRef: string;
  status: "draft" | "active" | "expired" | "revoked";
}
export interface RevenueAllocation {
  allocationId: string;
  assetId: string;
  projectId: string;
  grossRevenueCents: number;
  currency: string;
  allocationBasis: "fixed-contract" | "royalty-contract" | "equity-contract" | "unassigned";
  rateBasisPoints?: number;
  contractRef?: string;
  computedShareCents: number | null;
  status: "proposed" | "contract-verified" | "payable" | "disputed" | "not-applicable";
  notes: string[];
}
