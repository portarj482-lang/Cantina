import type { TemporalMapping } from "./conversions.ts";
import type { TemporalValue } from "./types.ts";

/**
 * An explicit mapping registry. Registration is an administrative action in
 * this prototype; production must put it behind authenticated review.
 */
export class TemporalMappingRegistry {
  private readonly mappings = new Map<string, TemporalMapping>();

  register(mapping: TemporalMapping): void {
    if (!mapping.id.trim()) throw new Error("Mapping id is required");
    if (this.mappings.has(mapping.id)) throw new Error(`Mapping already registered: ${mapping.id}`);
    if (!mapping.assumptions.length) throw new Error("Mappings must document assumptions");
    if (!mapping.limitations.length) throw new Error("Mappings must document limitations");
    this.mappings.set(mapping.id, { ...mapping, assumptions: [...mapping.assumptions], evidenceIds: [...mapping.evidenceIds], limitations: [...mapping.limitations] });
  }

  get(id: string): TemporalMapping | undefined {
    const mapping = this.mappings.get(id);
    return mapping ? { ...mapping, assumptions: [...mapping.assumptions], evidenceIds: [...mapping.evidenceIds], limitations: [...mapping.limitations] } : undefined;
  }

  find(from: TemporalValue["basis"], to: TemporalValue["basis"]): TemporalMapping[] {
    return [...this.mappings.values()]
      .filter((mapping) => mapping.from === from && mapping.to === to)
      .map((mapping) => ({ ...mapping, assumptions: [...mapping.assumptions], evidenceIds: [...mapping.evidenceIds], limitations: [...mapping.limitations] }));
  }

  listIds(): string[] {
    return [...this.mappings.keys()].sort();
  }
}
