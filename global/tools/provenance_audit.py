"""Flag claim sentences in finding files that lack a provenance tag or use banned wording.

Usage: python3 -I provenance_audit.py <findings_dir>
Exit 0: clean. Exit 1: flags found. Exit 2: bad usage, missing folder, or no finding files.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

TAG: re.Pattern[str] = re.compile(
    r"\[(?:SRC|TOOL|POC|WEB|USER|ASSUMPTION|UNKNOWN|REF)(?:[:\s][^\]]*)?\]"
)
BANNED: re.Pattern[str] = re.compile(
    r"\b(very|highly|extremely|significant|secure|safe|guaranteed|fully|robust)\b",
    re.IGNORECASE,
)
LABEL: re.Pattern[str] = re.compile(r"^\*\*[^*]+:\*\*\s*")
CHECKBOX: re.Pattern[str] = re.compile(r"^\[[ xX]\]\s*")
SENTENCE_END: re.Pattern[str] = re.compile(r"(?<=[.!?])\s+")
SEPARATOR: re.Pattern[str] = re.compile(r"^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?$")
SKIP_PREFIXES: tuple[str, ...] = ("#", "<")


def table_cells(line: str) -> list[str]:
    """Return the non-empty cells of one markdown table row."""
    return [cell.strip() for cell in line.strip().strip("|").split("|") if cell.strip()]


def prose_lines(text: str) -> list[str]:
    """Return every line that can carry a claim: prose, bullets, checklist items, and table cells.

    Headings, code blocks, HTML lines, horizontal rules, and table header rows are skipped.
    """
    lines: list[str] = []
    raw_lines: list[str] = text.splitlines()
    in_code = False
    for index, raw in enumerate(raw_lines):
        line = raw.strip()
        if line.startswith("```"):
            in_code = not in_code
            continue
        if in_code or not line or line.startswith(SKIP_PREFIXES) or SEPARATOR.match(line):
            continue
        if line.startswith("|"):
            next_line = raw_lines[index + 1].strip() if index + 1 < len(raw_lines) else ""
            if SEPARATOR.match(next_line):
                continue
            for cell in table_cells(line):
                cleaned = LABEL.sub("", cell)
                if cleaned:
                    lines.append(cleaned)
            continue
        if line.startswith("- "):
            line = line[2:]
        line = CHECKBOX.sub("", line)
        line = LABEL.sub("", line)
        if line:
            lines.append(line)
    return lines


def audit_file(path: Path) -> list[dict[str, str]]:
    """Return one flag per untagged sentence and one per banned word found."""
    flags: list[dict[str, str]] = []
    for line in prose_lines(path.read_text(encoding="utf-8")):
        for sentence in SENTENCE_END.split(line):
            sentence = sentence.strip()
            if not sentence:
                continue
            if not TAG.search(sentence):
                flags.append({"file": path.name, "problem": "untagged", "text": sentence})
            for match in BANNED.finditer(sentence):
                flags.append({
                    "file": path.name,
                    "problem": f"banned:{match.group(0).lower()}",
                    "text": sentence,
                })
    return flags


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: provenance_audit.py <findings_dir>", file=sys.stderr)
        return 2
    folder = Path(argv[1])
    if not folder.is_dir():
        print(f"findings folder not found: {folder}", file=sys.stderr)
        return 2
    files = sorted(folder.glob("F-*.md"))
    if not files:
        print(f"no F-*.md files in {folder}; nothing audited", file=sys.stderr)
        return 2
    flags: list[dict[str, str]] = []
    for path in files:
        flags.extend(audit_file(path))
    report = {"files_checked": len(files), "count": len(flags), "flags": flags}
    print(json.dumps(report, indent=2))
    return 1 if flags else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
