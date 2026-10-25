import { randomUUID } from "node:crypto";
import type { ConsentScope, LicenseGrant, RevenueAllocation, RightsAsset } from "./types.ts";

export class RightsRegistry {
  private assets = new Map<string, RightsAsset>();
  private grants = new Map<string, LicenseGrant>();
  private allocations = new Map<string, RevenueAllocation>();

  registerAsset(input: Omit<RightsAsset, "assetId">): RightsAsset {
    if (!input.title.trim() || !input.creator.trim() || !input.description.trim()) throw new Error("Asset title, creator, and description are required.");
    if (input.status === "approved-for-use" && (input.evidenceRefs.length === 0 || input.provenanceRefs.length === 0)) throw new Error("Approval requires provenance and evidence references.");
    const asset: RightsAsset = { ...structuredClone(input), assetId: randomUUID() };
    this.assets.set(asset.assetId, asset);
    return structuredClone(asset);
  }
  getAsset(id: string): RightsAsset | undefined { const x = this.assets.get(id); return x ? structuredClone(x) : undefined; }

  addGrant(input: Omit<LicenseGrant, "grantId">): LicenseGrant {
    const asset = this.assets.get(input.assetId);
    if (!asset) throw new Error("Unknown rights asset.");
    if (!input.licensor.trim() || !input.licensee.trim() || !input.signedDocumentRef.trim()) throw new Error("Grant parties and signed-document reference are required.");
    if (input.status === "active" && input.scope.some(scope => !asset.permittedScopes.includes(scope) || asset.excludedScopes.includes(scope))) throw new Error("Grant scope exceeds the asset's documented permitted scope.");
    if (input.endDate && input.endDate < input.startDate) throw new Error("Grant end date precedes start date.");
    const grant: LicenseGrant = { ...structuredClone(input), grantId: randomUUID() };
    this.grants.set(grant.grantId, grant);
    return structuredClone(grant);
  }
  activeGrantFor(assetId: string, licensee: string, scope: ConsentScope, at = new Date().toISOString().slice(0, 10)): LicenseGrant | undefined {
    const grant = [...this.grants.values()].find(g => g.assetId === assetId && g.licensee === licensee && g.status === "active" && g.scope.includes(scope) && g.startDate <= at && (!g.endDate || g.endDate >= at));
    return grant ? structuredClone(grant) : undefined;
  }
  recordRevenue(input: Omit<RevenueAllocation, "allocationId" | "computedShareCents">): RevenueAllocation {
    if (!Number.isSafeInteger(input.grossRevenueCents) || input.grossRevenueCents < 0) throw new Error("Gross revenue must be a non-negative integer number of cents.");
    if (!/^[A-Z]{3}$/.test(input.currency)) throw new Error("Currency must be an ISO-style three-letter uppercase code.");
    let share: number | null = null;
    if (input.allocationBasis === "royalty-contract") {
      if (!input.contractRef || !Number.isInteger(input.rateBasisPoints) || input.rateBasisPoints! < 0 || input.rateBasisPoints! > 10000) throw new Error("Royalty calculation requires a contract reference and rate between 0 and 10000 basis points.");
      share = Math.floor(input.grossRevenueCents * input.rateBasisPoints! / 10000);
      if (input.status === "payable" && !input.contractRef) throw new Error("Payable status requires a verified contract reference.");
    } else if (input.allocationBasis === "fixed-contract" || input.allocationBasis === "equity-contract") {
      // These arrangements need their own contract terms; do not infer an amount from an unspecified contract.
      if (input.status === "payable") throw new Error("Fixed and equity allocations require contract-specific calculation outside this generic module.");
    }
    const allocation: RevenueAllocation = { ...structuredClone(input), allocationId: randomUUID(), computedShareCents: share };
    this.allocations.set(allocation.allocationId, allocation);
    return structuredClone(allocation);
  }
}
