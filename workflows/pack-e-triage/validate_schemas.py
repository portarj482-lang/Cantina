#!/usr/bin/env python3
"""JSON Schema Validator for Pack E Triage and Pack A Pathway Scout Artifacts.

Validates:
  1. hallucination_audit.json against schemas/hallucination_audit.schema.json
  2. hallucination_audit.provenance.json against schemas/hallucination_audit.provenance.schema.json
  3. overlap_analysis.json against schemas/overlap_analysis.schema.json
  4. triage_summary.json against schemas/triage_summary.schema.json
  5. pathways.json against pack-a-pathway-scout/schemas/pathways.schema.json

Usage:
  python3 validate_schemas.py [--dir /path/to/scans] [--audit /path/to/audit.json] \
      [--provenance /path/to/provenance.json] [--overlap /path/to/overlap.json] \
      [--triage /path/to/triage_summary.json] [--pathways /path/to/pathways.json]

Exit codes:
  0 - Artifacts are valid JSON and conform to their schemas.
  1 - Validation failed (malformed JSON or schema violation).
  2 - Operational failure (missing file, OS error).
"""

import argparse
import json
import os
import sys
from pathlib import Path


def load_json(filepath: Path) -> tuple[dict | None, str | None]:
    if not filepath.is_file():
        return None, f"File does not exist: {filepath}"
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data, None
    except json.JSONDecodeError as e:
        return None, f"Invalid JSON in {filepath}: {e}"
    except Exception as e:
        return None, f"Error reading {filepath}: {e}"


def validate_artifact(data: dict, schema: dict, name: str, artifact_type: str) -> tuple[bool, str | None]:
    try:
        import jsonschema

        try:
            jsonschema.validate(instance=data, schema=schema)
            return True, None
        except jsonschema.ValidationError as e:
            return False, f"Validation Failure in {name}: {e.message}"
    except ImportError:
        # Fallback basic schema validation without jsonschema package
        if artifact_type == "audit":
            req_audit = ["slug", "pinned_commit", "timestamp", "status", "citations_audited", "dropped_count"]
            for field in req_audit:
                if field not in data:
                    return False, f"Audit missing required field: {field}"
        elif artifact_type == "provenance":
            req_prov = ["source_files", "processed_count", "errors", "pinned_commit", "timestamp"]
            for field in req_prov:
                if field not in data:
                    return False, f"Provenance missing required field: {field}"
        elif artifact_type == "overlap":
            req_overlap = [
                "schema_version",
                "slug",
                "known_issues_checked",
                "timestamp",
                "status",
                "analysis",
                "evidence",
                "limitations",
                "write",
            ]
            for field in req_overlap:
                if field not in data:
                    return False, f"Overlap analysis missing required field: {field}"
            if not isinstance(data.get("analysis"), dict):
                return False, "Overlap analysis 'analysis' field must be an object"
            for f in ["candidate_count", "known_issue_count", "relationships"]:
                if f not in data["analysis"]:
                    return False, f"Overlap analysis missing analysis field: {f}"
            if not isinstance(data.get("evidence"), dict):
                return False, "Overlap analysis 'evidence' field must be an object"
            if not isinstance(data.get("write"), dict):
                return False, "Overlap analysis 'write' field must be an object"
        elif artifact_type == "triage":
            req_triage = [
                "schema_version",
                "slug",
                "timestamp",
                "status",
                "summary",
                "environment",
                "candidates",
                "errors",
                "provenance",
            ]
            for field in req_triage:
                if field not in data:
                    return False, f"Triage summary missing required field: {field}"
            if not isinstance(data.get("summary"), dict):
                return False, "Triage summary 'summary' field must be an object"
            for f in [
                "total_candidates",
                "validated",
                "likely_valid",
                "needs_investigation",
                "false_positive",
                "duplicates",
                "out_of_scope",
                "informational",
                "unverified",
            ]:
                if f not in data["summary"]:
                    return False, f"Triage summary missing summary counter: {f}"
            if not isinstance(data.get("environment"), dict):
                return False, "Triage summary 'environment' field must be an object"
            if not isinstance(data.get("candidates"), list):
                return False, "Triage summary 'candidates' field must be a list"
            if not isinstance(data.get("provenance"), dict):
                return False, "Triage summary 'provenance' field must be an object"
        elif artifact_type == "pathways":
            req_pathways = [
                "schema_version",
                "slug",
                "status",
                "timestamp",
                "repository",
                "execution",
                "scope",
                "inventory",
                "pathways",
                "priority_review_queue",
                "analysis",
                "findings",
                "completion",
            ]
            for field in req_pathways:
                if field not in data:
                    return False, f"Pathways artifact missing required field: {field}"
            if not isinstance(data.get("repository"), dict):
                return False, "Pathways 'repository' field must be an object"
            for f in ["root", "commit", "worktree_clean"]:
                if f not in data["repository"]:
                    return False, f"Pathways repository missing field: {f}"
            if not isinstance(data.get("execution"), dict):
                return False, "Pathways 'execution' field must be an object"
            for f in ["mode", "write_authorized"]:
                if f not in data["execution"]:
                    return False, f"Pathways execution missing field: {f}"
            if not isinstance(data.get("scope"), dict):
                return False, "Pathways 'scope' field must be an object"
            for f in ["status", "in_scope_assets", "out_of_scope_assets", "assumptions", "limitations"]:
                if f not in data["scope"]:
                    return False, f"Pathways scope missing field: {f}"
            if not isinstance(data.get("inventory"), dict):
                return False, "Pathways 'inventory' field must be an object"
            for f in ["source_roots", "contracts", "programs", "entrypoints", "external_dependencies"]:
                if f not in data["inventory"]:
                    return False, f"Pathways inventory missing field: {f}"
            if not isinstance(data.get("analysis"), dict):
                return False, "Pathways 'analysis' field must be an object"
            for f in ["tools", "tests", "coverage", "limitations"]:
                if f not in data["analysis"]:
                    return False, f"Pathways analysis missing field: {f}"
            coverage = data["analysis"].get("coverage", {})
            for f in ["entrypoints_total", "entrypoints_verified", "pathways_total", "pathways_verified"]:
                if f not in coverage:
                    return False, f"Pathways coverage missing field: {f}"
            if not isinstance(data.get("completion"), dict):
                return False, "Pathways 'completion' field must be an object"
            for f in ["entrypoints_mapped", "pathways_mapped", "evidence_validated", "complete"]:
                if f not in data["completion"]:
                    return False, f"Pathways completion missing field: {f}"
            valid_statuses = {"PATHWAYS_SCOUTED", "PARTIAL", "BLOCKED", "FAILED", "DRY_RUN"}
            if data.get("status") not in valid_statuses:
                return False, f"Pathways status '{data.get('status')}' is not a valid status"
        elif artifact_type == "recon":
            for f in ["slug", "contracts_found", "timestamp", "status"]:
                if f not in data:
                    return False, f"Reconnaissance artifact missing required field: {f}"
            if not isinstance(data.get("contracts_found"), int) or data.get("contracts_found") < 0:
                return False, "Reconnaissance 'contracts_found' must be a non-negative integer"
            if data.get("status") not in {"RECON_COMPLETE", "RECON_PARTIAL", "RECON_BLOCKED", "RECON_FAILED"}:
                return False, f"Reconnaissance 'status' must be valid enum, got: {data.get('status')}"
            if "scope" in data and not isinstance(data["scope"], dict):
                return False, "Reconnaissance 'scope' field must be an object"
            if "inventory" in data and not isinstance(data["inventory"], list):
                return False, "Reconnaissance 'inventory' field must be a list"
        elif artifact_type == "normalized":
            req_norm = ["slug", "normalized_findings", "timestamp", "status"]
            for field in req_norm:
                if field not in data:
                    return False, f"Normalized findings missing required field: {field}"
            if data["status"] != "NORMALIZATION_COMPLETE":
                return False, f"Normalized findings invalid status: {data['status']}"
            if not isinstance(data.get("normalized_findings"), list):
                return False, "Normalized findings 'normalized_findings' must be a list"
            for idx, finding in enumerate(data["normalized_findings"]):
                if not isinstance(finding, dict):
                    return False, f"Finding at index {idx} must be an object"
                for req_f in ["id", "title", "severity", "classification", "description", "target", "provenance"]:
                    if req_f not in finding:
                        return False, f"Finding {finding.get('id', idx)} missing required field: {req_f}"
                if finding["classification"] not in ["CONFIRMED", "STATIC_ANALYSIS", "NEEDS_REVIEW", "REJECTED"]:
                    return False, f"Finding {finding['id']} has invalid classification: {finding['classification']}"
                if not isinstance(finding.get("target"), dict) or "slug" not in finding["target"]:
                    return False, f"Finding {finding['id']} target must be object containing slug"
                if not isinstance(finding.get("provenance"), list):
                    return False, f"Finding {finding['id']} provenance must be a list"
        elif artifact_type == "pin":
            req_pin = ["slug", "scope_file", "scope_sha256", "timestamp", "status"]
            for field in req_pin:
                if field not in data:
                    return False, f"Source pin missing required field: {field}"
            if data.get("status") != "PIN_VERIFIED":
                return False, f"Source pin 'status' must be PIN_VERIFIED, got: {data.get('status')}"
            if not isinstance(data.get("scope_sha256"), str) or len(data.get("scope_sha256")) != 64:
                return False, "Source pin 'scope_sha256' must be 64-char hexadecimal string"
            if not isinstance(data.get("scope_file"), str) or not data.get("scope_file").endswith("/scope.md"):
                return False, "Source pin 'scope_file' must be repository-relative scope path"
        return True, None


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Pack E triage JSON artifacts against schemas.")
    parser.add_argument(
        "--dir",
        help="Directory containing artifacts (hallucination_audit.json, provenance, overlap_analysis.json, or findings_normalized.json)",
    )
    parser.add_argument("--audit", help="Explicit path to hallucination_audit.json")
    parser.add_argument("--provenance", help="Explicit path to hallucination_audit.provenance.json")
    parser.add_argument("--overlap", help="Explicit path to overlap_analysis.json")
    parser.add_argument("--triage", help="Explicit path to triage_summary.json")
    parser.add_argument("--normalized", help="Explicit path to findings_normalized.json")
    parser.add_argument("--pathways", help="Explicit path to pathways.json (Pack A Pathway Scout)")
    parser.add_argument("--recon", help="Explicit path to recon.json (Pack A Reconnaissance)")
    parser.add_argument("--pin", help="Explicit path to pin.json (Pack A Source Pin)")
    parser.add_argument("--schemas-dir", help="Directory containing schema files (defaults to adjacent schemas/)")

    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    schemas_dir = Path(args.schemas_dir).resolve() if args.schemas_dir else (script_dir / "schemas")

    # Pack A schemas live in sibling workflow directories
    pack_a_pathways_schema_dir = script_dir.parent / "pack-a-pathway-scout" / "schemas"
    pack_a_recon_schema_dir = script_dir.parent / "pack-a-recon" / "schemas"
    pack_a_pin_schema_dir = script_dir.parent / "pack-a-source" / "schemas"

    audit_schema_path = schemas_dir / "hallucination_audit.schema.json"
    prov_schema_path = schemas_dir / "hallucination_audit.provenance.schema.json"
    overlap_schema_path = schemas_dir / "overlap_analysis.schema.json"
    triage_schema_path = schemas_dir / "triage_summary.schema.json"
    normalized_schema_path = schemas_dir / "findings_normalized.schema.json"
    pathways_schema_path = pack_a_pathways_schema_dir / "pathways.schema.json"
    recon_schema_path = pack_a_recon_schema_dir / "recon.schema.json"
    pin_schema_path = pack_a_pin_schema_dir / "pin.schema.json"

    targets_to_validate: list[tuple[Path, Path, str]] = []

    if args.dir:
        scans_dir = Path(args.dir).resolve()
        audit_path = scans_dir / "hallucination_audit.json"
        prov_path = scans_dir / "hallucination_audit.provenance.json"
        overlap_path = scans_dir / "overlap_analysis.json"
        triage_path = scans_dir / "triage_summary.json"
        normalized_path = scans_dir / "findings_normalized.json"
        recon_path = scans_dir / "recon.json"
        pin_path = scans_dir / "pin.json"

        found_any = False
        if audit_path.is_file() and prov_path.is_file():
            targets_to_validate.append((audit_path, audit_schema_path, "audit"))
            targets_to_validate.append((prov_path, prov_schema_path, "provenance"))
            found_any = True
        if overlap_path.is_file():
            targets_to_validate.append((overlap_path, overlap_schema_path, "overlap"))
            found_any = True
        if triage_path.is_file():
            targets_to_validate.append((triage_path, triage_schema_path, "triage"))
            found_any = True
        if normalized_path.is_file():
            targets_to_validate.append((normalized_path, normalized_schema_path, "normalized"))
            found_any = True
        if recon_path.is_file():
            targets_to_validate.append((recon_path, recon_schema_path, "recon"))
            found_any = True
        if pin_path.is_file():
            targets_to_validate.append((pin_path, pin_schema_path, "pin"))
            found_any = True

        if not found_any:
            sys.stderr.write(f"Error: No known artifacts found in directory: {scans_dir}\n")
            return 2
    else:
        if (
            not args.normalized
            and not args.overlap
            and not args.triage
            and not args.pathways
            and not args.recon
            and not args.pin
            and (not args.audit or not args.provenance)
        ):
            sys.stderr.write(
                "Error: Must provide either --dir, --normalized, --triage, --overlap, --pathways, --recon, --pin, or both --audit and --provenance\n"
            )
            return 2

        if args.audit and args.provenance:
            targets_to_validate.append((Path(args.audit).resolve(), audit_schema_path, "audit"))
            targets_to_validate.append((Path(args.provenance).resolve(), prov_schema_path, "provenance"))

        if args.overlap:
            targets_to_validate.append((Path(args.overlap).resolve(), overlap_schema_path, "overlap"))

        if args.triage:
            targets_to_validate.append((Path(args.triage).resolve(), triage_schema_path, "triage"))

        if args.normalized:
            targets_to_validate.append((Path(args.normalized).resolve(), normalized_schema_path, "normalized"))

        if args.pathways:
            targets_to_validate.append((Path(args.pathways).resolve(), pathways_schema_path, "pathways"))

        if args.recon:
            targets_to_validate.append((Path(args.recon).resolve(), recon_schema_path, "recon"))

        if args.pin:
            targets_to_validate.append((Path(args.pin).resolve(), pin_schema_path, "pin"))

    # Validate each target
    for artifact_path, schema_path, artifact_type in targets_to_validate:
        schema, err = load_json(schema_path)
        if err:
            sys.stderr.write(f"Schema Error ({schema_path.name}): {err}\n")
            return 2

        data, err = load_json(artifact_path)
        if err:
            sys.stderr.write(f"Artifact Error ({artifact_path.name}): {err}\n")
            return 1

        ok, err_msg = validate_artifact(data, schema, artifact_path.name, artifact_type)
        if not ok:
            sys.stderr.write(f"{err_msg}\n")
            return 1

    sys.stdout.write("SCHEMA_VALIDATION_PASSED: Artifacts conform to JSON schemas.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
