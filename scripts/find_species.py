#!/usr/bin/env python3
"""Search the cover crop species gazetteer (data_catalog.yml) by keyword.

Usage:
    python scripts/find_species.py <keyword>

Example:
    python scripts/find_species.py vetch
    -> Vicia sativa (Common vetch) [Fabaceae, Legume]
       Vicia villosa (Hairy vetch) [Fabaceae, Legume]
       Lathyrus sativus (Chickling vetch) [Fabaceae, Legume]
"""
from __future__ import annotations

import sys
from pathlib import Path

_repo_root = next(p for p in Path(__file__).resolve().parents
                  if (p / "src" / "literature_extractor.py").exists())
sys.path.insert(0, str(_repo_root))

from src.literature_extractor import load_data_catalog


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__, file=sys.stderr)
        return 2

    keyword = argv[0].lower()
    catalog = load_data_catalog()
    hits = []
    for entry in catalog["species_gazetteer"]:
        names = [entry["scientific_name"], *entry.get("common_names", [])]
        if any(keyword in n.lower() for n in names):
            hits.append(entry)

    if not hits:
        print(f"No match for '{keyword}' in the gazetteer.")
        print("If this is a real species from a paper you're processing, add it to")
        print("data_catalog.yml with a real source — do not let the LLM guess it.")
        return 1

    for entry in hits:
        common = ", ".join(entry.get("common_names", []))
        print(f"{entry['scientific_name']} ({common}) [{entry['family']}, {entry['cc_category']}]")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
