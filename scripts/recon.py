#!/usr/bin/env python3
"""Pack A — Reconnaissance Engine Wrapper
Delegates to workflows/pack-a-recon/recon.py
"""
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
RECON_ENGINE = REPO_ROOT / "workflows" / "pack-a-recon" / "recon.py"

if __name__ == "__main__":
    import runpy
    sys.path.insert(0, str(RECON_ENGINE.parent))
    runpy.run_path(str(RECON_ENGINE), run_name="__main__")
