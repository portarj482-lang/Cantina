"""Synthetic report adapter extracting citation candidates from markdown / text reports.

Interface:
    extract_citations(report_path: str) -> list[dict]

Extracts citations formatted as:
    CITE: <target_path>:<start_line>-<end_line>
    CITE: <target_path>:<line_number>
"""

import os
import re
from typing import List, Dict, Any

MAX_REPORT_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB limit
MAX_CITATIONS_PER_REPORT = 10000

CITE_PATTERN = re.compile(r"^(?:[-*>]|\d+\.)?\s*CITE:\s*(.+?):(\d+)(?:-(\d+))?\s*$")


def extract_citations(report_path: str) -> List[Dict[str, Any]]:
    """Extract normalized citation candidates from one report file.

    Returns:
        List of citation dicts:
        {
            "target": str,
            "start_line": int,
            "end_line": int,
            "reported_in": str
        }
    """
    if not os.path.isfile(report_path):
        raise FileNotFoundError(f"Report file not found: {report_path}")

    file_size = os.path.getsize(report_path)
    if file_size > MAX_REPORT_SIZE_BYTES:
        raise ValueError(
            f"Report file {report_path} exceeds maximum allowed size ({file_size} > {MAX_REPORT_SIZE_BYTES} bytes)"
        )

    citations: List[Dict[str, Any]] = []

    with open(report_path, "r", encoding="utf-8", errors="replace") as f:
        for line_num, line in enumerate(f, start=1):
            line_str = line.strip()
            if not line_str.startswith("CITE:"):
                # Also check inline CITE: if line has whitespace prefix
                match = CITE_PATTERN.match(line)
            else:
                match = CITE_PATTERN.match(line_str)

            if match:
                target = match.group(1)
                start_str = match.group(2)
                end_str = match.group(3)

                start_line = int(start_str)
                end_line = int(end_str) if end_str is not None else start_line

                citations.append(
                    {
                        "target": target,
                        "start_line": start_line,
                        "end_line": end_line,
                        "reported_in": report_path,
                    }
                )

                if len(citations) >= MAX_CITATIONS_PER_REPORT:
                    break

    return citations
