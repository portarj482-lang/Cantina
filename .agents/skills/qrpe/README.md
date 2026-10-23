# QRPE: Quantum Recursive Pipeline Engineer Skill

Autonomous systems architecture, verification engine, registry reconciler, and self-auditing control plane for Cantina smart-contract security infrastructure.

## Structure
- `SKILL.md`: Authoritative operational instructions and recursive control loops.
- `manifest.yml`: Machine-readable skill descriptor.
- `schemas/`: Canonical JSON Schemas for audit records, evidence, divergence reports, and handoffs.
- `sandboxes/`: Sandbox execution boundary profiles.
- `adapters/`: Deterministic execution adapters with command flag verification and SHA-256 evidence generation.

## Usage
Execute adapters with `--dry-run` to preview commands without side effects:
```bash
python3 adapters/slither_adapter.py --target /path/to/build --output-dir scans/slither --dry-run
python3 adapters/foundry_adapter.py --target /path/to/build --output-dir scans/forge --dry-run
```
To execute verified scans, pass `--confirm`.
