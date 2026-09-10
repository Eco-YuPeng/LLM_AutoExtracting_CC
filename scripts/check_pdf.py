#!/usr/bin/env python3
"""Pre-flight check: is this PDF readable before committing to a full
extraction run?

Usage:
    python scripts/check_pdf.py <path1.pdf> <path2.pdf> ...

Exit code 0 if ALL PDFs are readable, 1 if ANY failed.
"""
from __future__ import annotations

import sys
from pathlib import Path

_repo_root = next(p for p in Path(__file__).resolve().parents
                  if (p / "src" / "literature_extractor.py").exists())
sys.path.insert(0, str(_repo_root))

from src.literature_extractor import check_pdf_readable


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__, file=sys.stderr)
        return 2

    any_failed = False
    for path_str in argv:
        ok, msg = check_pdf_readable(Path(path_str))
        if ok:
            print(f"OK   {path_str} ({msg})")
        else:
            any_failed = True
            print(f"FAIL {path_str}")
            print(f"         {msg}")

    if any_failed:
        print("\nSome PDFs failed. Do not run the workflow on a failed PDF —")
        print("tell the user which file and why (AGENTS.md: Failure Handling).")

    return 1 if any_failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
