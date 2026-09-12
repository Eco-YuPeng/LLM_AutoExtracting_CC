"""
Build an initial cover-crop species normalization table (tiers 2-4 of the
4-tier scheme: common name / taxonomic family / functional group) from
the two hand-digitized ground-truth spreadsheets (YieldTable.xlsx,
GHGTable.xlsx).

Tier 1 (verbatim original wording from each paper) is NOT built here --
neither spreadsheet records the paper's exact original phrase, only an
already-normalized common name, so tier 1 can only come from a fresh
LLM read of each paper's own text.

Source columns used:
  YieldTable  CCs Species   -> tier 2 (common name), cleanest source
              Unnamed: 12   -> tier 3 (family) -- only ~6% filled
              CCs Famaily   -> tier 4 (functional group; column name is
                                a typo in the source file, content is
                                legume/non-legume/mixture/rotation)
  GHGTable    cover_crop_species -> tier 2 candidate, noisier text
              cover_crop_types   -> tier 4 candidate, BUT the column
                                mixes two incompatible vocabularies
                                (legume/non-legume/mixture in most rows,
                                but plain "Y"/"N" in ~27 rows) -- the
                                "Y"/"N" rows are flagged, never merged
                                into the legume/non-legume vocabulary.

A canonical entry's family/functional-group is filled only when a
source table actually states it; everything else is marked
NEEDS_CONFIRMATION rather than guessed, per the project's no-fabrication
rule (AGENTS.md).  Near-duplicate spellings (e.g. a typo like "Ceral
Rye" vs "Cereal Rye") are NOT auto-merged -- they are listed separately
in possible_near_duplicates.csv for a human decision, so two genuinely
different entries never get silently collapsed.
"""
import os
import re
import difflib
from pathlib import Path
from collections import defaultdict

import pandas as pd

_DEFAULT_DIR = "/Users/yupe4788/Library/CloudStorage/OneDrive-UCB-O365/1.Research 4.49.41 PM/1. Main Project/7. CC maps"
# GHG.xlsx's "Deduplicated" sheet is the authoritative, human-reviewed GHG
# ground truth (confirmed 2026-09-11) -- GHGTable.xlsx / Sheet1 is a prior,
# noisier pass that Deduplicated supersedes; every other sheet in GHG.xlsx
# (Prior MetaData Cleaning Record, Prior Meta Paper List, Original Meta,
# Dictionary, Sheet2, Sheet3) is audit/process trail that feeds Deduplicated,
# not itself a data source.
GHG_XLSX = Path(os.environ.get("GHG_XLSX_PATH", f"{_DEFAULT_DIR}/GHG.xlsx"))
YIELD_XLSX = Path(os.environ.get("YIELD_XLSX_PATH", f"{_DEFAULT_DIR}/YieldTable.xlsx"))
OUT_DIR = Path(__file__).resolve().parents[1] / "output"

VALID_FUNCTIONAL_GROUPS = {"legume", "non-legume", "mixture", "rotation"}
CANONICAL_CASE = {"legume": "Legume", "non-legume": "Non-legume",
                   "mixture": "Mixture", "rotation": "Rotation"}


def norm_key(s: str) -> str:
    s = str(s).strip().lower()
    s = re.sub(r"\s+", " ", s)
    return s


def main() -> None:
    yld = pd.read_excel(YIELD_XLSX, sheet_name="Yield Record")
    ghg = pd.read_excel(GHG_XLSX, sheet_name="Deduplicated")

    entries = defaultdict(lambda: {
        "raw_variants": set(),
        "yield_count": 0,
        "ghg_count": 0,
        "family_values": set(),
        "functional_group_values": set(),
        "functional_group_needs_review_raw": set(),  # e.g. stray Y/N codes
        "type_values": set(),
    })

    # --- YieldTable pass ---
    for _, row in yld.iterrows():
        raw = row.get("CCs Species")
        if pd.isna(raw) or not str(raw).strip():
            continue
        key = norm_key(raw)
        e = entries[key]
        e["raw_variants"].add(str(raw).strip())
        e["yield_count"] += 1
        fam = row.get("Unnamed: 12")
        if pd.notna(fam) and str(fam).strip():
            e["family_values"].add(str(fam).strip())
        fg = row.get("CCs Famaily")
        if pd.notna(fg) and str(fg).strip():
            fg_norm = str(fg).strip()
            if fg_norm.lower() in VALID_FUNCTIONAL_GROUPS:
                e["functional_group_values"].add(CANONICAL_CASE[fg_norm.lower()])
            else:
                e["functional_group_needs_review_raw"].add(fg_norm)
        t = row.get("CCs Type")
        if pd.notna(t) and str(t).strip():
            e["type_values"].add(str(t).strip())

    # --- GHG.xlsx "Deduplicated" pass (authoritative GHG ground truth) ---
    for _, row in ghg.iterrows():
        raw = row.get("CC_species")
        if pd.isna(raw) or not str(raw).strip():
            continue
        key = norm_key(raw)
        e = entries[key]
        e["raw_variants"].add(str(raw).strip())
        e["ghg_count"] += 1
        fg = row.get("CC_types")
        if pd.notna(fg) and str(fg).strip():
            fg_norm = str(fg).strip()
            if fg_norm.lower() in VALID_FUNCTIONAL_GROUPS:
                e["functional_group_values"].add(CANONICAL_CASE[fg_norm.lower()])
            else:
                e["functional_group_needs_review_raw"].add(fg_norm)

    # --- assemble canonical table ---
    rows_out = []
    for key, e in entries.items():
        # prefer the most-common original casing as the tier-2 canonical label
        canonical = sorted(e["raw_variants"])[0]
        family = "; ".join(sorted(e["family_values"])) if e["family_values"] else "NEEDS_CONFIRMATION"
        if len(e["family_values"]) > 1:
            family += " [MULTIPLE_VALUES_REVIEW]"
        func_group = "; ".join(sorted(e["functional_group_values"])) if e["functional_group_values"] else "NEEDS_CONFIRMATION"
        if len(e["functional_group_values"]) > 1:
            func_group += " [MULTIPLE_VALUES_REVIEW]"
        rows_out.append({
            "tier2_common_name": canonical,
            "tier3_family": family,
            "tier4_functional_group": func_group,
            "functional_group_raw_needs_review": "; ".join(sorted(e["functional_group_needs_review_raw"])) or "",
            "cc_type_values_seen": "; ".join(sorted(e["type_values"])) or "",
            "yield_table_count": e["yield_count"],
            "ghg_table_count": e["ghg_count"],
            "raw_variants_seen": "; ".join(sorted(e["raw_variants"])),
        })

    out = pd.DataFrame(rows_out).sort_values(
        by=["yield_table_count", "ghg_table_count"], ascending=False
    ).reset_index(drop=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT_DIR / "species_normalization_table.csv", index=False)

    # --- near-duplicate spelling check (never auto-merged, human decides) ---
    keys = list(entries.keys())
    dup_rows = []
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            ratio = difflib.SequenceMatcher(None, keys[i], keys[j]).ratio()
            if ratio >= 0.82:
                dup_rows.append({
                    "entry_a": sorted(entries[keys[i]]["raw_variants"])[0],
                    "entry_b": sorted(entries[keys[j]]["raw_variants"])[0],
                    "similarity": round(ratio, 3),
                })
    dup_out = pd.DataFrame(dup_rows).sort_values("similarity", ascending=False)
    dup_out.to_csv(OUT_DIR / "possible_near_duplicates.csv", index=False)

    print(f"Canonical species entries: {len(out)}")
    print(f"  with family filled:            {(out['tier3_family'] != 'NEEDS_CONFIRMATION').sum()}")
    print(f"  with functional group filled:  {(out['tier4_functional_group'] != 'NEEDS_CONFIRMATION').sum()}")
    print(f"Possible near-duplicate spelling pairs flagged: {len(dup_out)}")
    print(f"\nWritten to {OUT_DIR}/species_normalization_table.csv")
    print(f"Written to {OUT_DIR}/possible_near_duplicates.csv")


if __name__ == "__main__":
    main()
