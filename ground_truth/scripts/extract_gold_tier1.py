"""
Split GHG.xlsx's "Deduplicated" sheet into two trust tiers (confirmed
2026-09-11): the 52 rows Yu Peng personally checked against the original
paper ("manul checked & revised" == "y") are TIER 1 -- the highest-trust
gold subset, to seed and prioritize the extraction-agent eval harness.
The remaining 437 rows (mostly reused from four prior published
meta-analyses, plus a smaller batch from a fresh WoS search) are TIER 2 --
useful reference, but not independently re-verified against the source
text by this project, so weighted lower when scoring pipeline accuracy.
"""
import os
from pathlib import Path
import pandas as pd

_DEFAULT_DIR = "/Users/yupe4788/Library/CloudStorage/OneDrive-UCB-O365/1.Research 4.49.41 PM/1. Main Project/7. CC maps"
GHG_XLSX = os.environ.get("GHG_XLSX_PATH", f"{_DEFAULT_DIR}/GHG.xlsx")
OUT_DIR = Path(__file__).resolve().parents[1] / "output"


def main() -> None:
    dd = pd.read_excel(GHG_XLSX, sheet_name="Deduplicated")
    tier1 = dd[dd["manul checked & revised"] == "y"].copy()
    tier2 = dd[dd["manul checked & revised"] != "y"].copy()

    tier1.to_csv(OUT_DIR / "ghg_gold_tier1_manually_verified.csv", index=False)
    tier2.to_csv(OUT_DIR / "ghg_gold_tier2_reference_only.csv", index=False)

    print(f"Tier 1 (manually verified, highest trust): {len(tier1)} rows, "
          f"{tier1['paper_id'].nunique()} papers")
    print(f"Tier 2 (reference only, lower trust):        {len(tier2)} rows, "
          f"{tier2['paper_id'].nunique()} papers")
    print(f"  of which from prior published meta-analyses (study_source 1-4): "
          f"{(tier2['study_source'] != 5).sum()} rows")
    print(f"  of which from this project's own WoS search (study_source 5):   "
          f"{(tier2['study_source'] == 5).sum()} rows")


if __name__ == "__main__":
    main()
