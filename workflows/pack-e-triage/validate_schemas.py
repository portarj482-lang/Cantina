#!/usr/bin/env python3
"""JSON Schema Validator for Pack E Triage Hallucination Audit Artifacts.

Validates:
  1. hallucination_audit.json against schemas/hallucination_audit.schema.json
  2. hallucination_audit.provenance.json against schemas/hallucination_audit.provenance.schema.json

Usage:
  python3 validate_schemas.py [--dir /path/to/scans] [--audit /path/to/audit.json] [--provenance /path/to/provenance.json]

Exit codes:
  0 - Both files are valid JSON and conform to their schemas.
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate hallucination audit JSON artifacts against schemas.")
    parser.add_argument("--dir", help="Directory containing both hallucination_audit.json and hallucination_audit.provenance.json")
    parser.add_argument("--audit", help="Explicit path to hallucination_audit.json")
    parser.add_argument("--provenance", help="Explicit path to hallucination_audit.provenance.json")
    parser.add_argument("--schemas-dir", help="Directory containing schema files (defaults to adjacent schemas/)")

    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    schemas_dir = Path(args.schemas_dir).resolve() if args.schemas_dir else (script_dir / "schemas")

    audit_schema_path = schemas_dir / "hallucination_audit.schema.json"
    prov_schema_path = schemas_dir / "hallucination_audit.provenance.schema.json"

    if args.dir:
        scans_dir = Path(args.dir).resolve()
        audit_path = scans_dir / "hallucination_audit.json"
        prov_path = scans_dir / "hallucination_audit.provenance.json"
    else:
        if not args.audit or not args.provenance:
            sys.stderr.write("Error: Must provide either --dir or both --audit and --provenance\n")
            return 2
        audit_path = Path(args.audit).resolve()
        prov_path = Path(args.provenance).resolve()

    # Load schemas
    audit_schema, err = load_json(audit_schema_path)
    if err:
        sys.stderr.write(f"Schema Error: {err}\n")
        return 2

    prov_schema, err = load_json(prov_schema_path)
    if err:
        sys.stderr.write(f"Schema Error: {err}\n")
        return 2

    # Load artifacts
    audit_data, err = load_json(audit_path)
    if err:
        sys.stderr.write(f"Audit Artifact Error: {err}\n")
        return 1

    prov_data, err = load_json(prov_path)
    if err:
        sys.stderr.write(f"Provenance Artifact Error: {err}\n")
        return 1

    # Validate using jsonschema if available, fallback to manual structure validation
    try:
        import jsonschema

        try:
            jsonschema.validate(instance=audit_data, schema=audit_schema)
        except jsonschema.ValidationError as e:
            sys.stderr.write(f"Validation Failure in {audit_path.name}: {e.message}\n")
            return 1

        try:
            jsonschema.validate(instance=prov_data, schema=prov_schema)
        except jsonschema.ValidationError as e:
            sys.stderr.write(f"Validation Failure in {prov_path.name}: {e.message}\n")
            return 1

        sys.stdout.write("SCHEMA_VALIDATION_PASSED: Both artifacts conform to JSON schemas.\n")
        return 0

    except ImportError:
        # Fallback basic schema validation without jsonschema package
        sys.stderr.write("Notice: jsonschema package not installed, performing basic field validation.\n")
        req_audit = ["slug", "pinned_commit", "timestamp", "status", "citations_audited", "dropped_count"]
        for field in req_audit:
            if field not in audit_data:
                sys.stderr.write(f"Audit missing required field: {field}\n")
                return 1

        req_prov = ["source_files", "processed_count", "errors", "pinned_commit", "timestamp"]
        for field in req_prov:
            if field not in prov_data:
                sys.stderr.write(f"Provenance missing required field: {field}\n")
                return 1

        sys.stdout.write("BASIC_SCHEMA_VALIDATION_PASSED\n")
        return 0


if __name__ == "__main__":
    sys.exit(main())
