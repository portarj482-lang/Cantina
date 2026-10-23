#!/usr/bin/env python3
"""JSON Schema Validator for Pack E Triage Artifacts.

Validates:
  1. hallucination_audit.json against schemas/hallucination_audit.schema.json
  2. hallucination_audit.provenance.json against schemas/hallucination_audit.provenance.schema.json
  3. overlap_analysis.json against schemas/overlap_analysis.schema.json
  4. triage_summary.json against schemas/triage_summary.schema.json

Usage:
  python3 validate_schemas.py [--dir /path/to/scans] [--audit /path/to/audit.json] [--provenance /path/to/provenance.json] [--overlap /path/to/overlap.json] [--triage /path/to/triage_summary.json]

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
    parser.add_argument("--schemas-dir", help="Directory containing schema files (defaults to adjacent schemas/)")

    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    schemas_dir = Path(args.schemas_dir).resolve() if args.schemas_dir else (script_dir / "schemas")

    audit_schema_path = schemas_dir / "hallucination_audit.schema.json"
    prov_schema_path = schemas_dir / "hallucination_audit.provenance.schema.json"
    overlap_schema_path = schemas_dir / "overlap_analysis.schema.json"
    triage_schema_path = schemas_dir / "triage_summary.schema.json"
    normalized_schema_path = schemas_dir / "findings_normalized.schema.json"

    targets_to_validate: list[tuple[Path, Path, str]] = []

    if args.dir:
        scans_dir = Path(args.dir).resolve()
        audit_path = scans_dir / "hallucination_audit.json"
        prov_path = scans_dir / "hallucination_audit.provenance.json"
        overlap_path = scans_dir / "overlap_analysis.json"
        triage_path = scans_dir / "triage_summary.json"
        normalized_path = scans_dir / "findings_normalized.json"

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

        if not found_any:
            sys.stderr.write(f"Error: No known artifacts found in directory: {scans_dir}\n")
            return 2
    else:
        if not args.normalized and not args.overlap and not args.triage and (not args.audit or not args.provenance):
            sys.stderr.write("Error: Must provide either --dir, --normalized, --triage, --overlap, or both --audit and --provenance\n")
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
