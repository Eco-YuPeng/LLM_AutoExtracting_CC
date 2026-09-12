"""
Produces the two human-facing review artifacts that came out of finalizing
species_normalization_table.csv:

  1. species_merge_decisions.csv -- ALL 24 near-duplicate pairs originally
     flagged, each with the action actually taken (MERGED / KEPT_SEPARATE /
     OPEN_REVIEW) and why, so Yu Peng can see -- and override -- every call,
     not just the ones that got merged.
  2. yieldtable_data_issues_for_review.csv -- source-data problems found in
     YieldTable.xlsx while building the species table (never silently fixed
     in the user's own spreadsheet): the 24 "Cereal Rye" rows mislabeled
     Legume, and the "Phacelia" -> Brassicaceae family mistag.
"""
import os
from pathlib import Path
import pandas as pd

OUT_DIR = Path(__file__).resolve().parents[1] / "output"
_DEFAULT_DIR = "/Users/yupe4788/Library/CloudStorage/OneDrive-UCB-O365/1.Research 4.49.41 PM/1. Main Project/7. CC maps"
YIELD_XLSX = os.environ.get("YIELD_XLSX_PATH", f"{_DEFAULT_DIR}/YieldTable.xlsx")

DECISIONS = [
    ("Ceral Rye + Hariy Vetch", "Ceral Rye + Hairy Vetch", "MERGED", "double typo (Ceral->Cereal implied, Hariy->Hairy) of the same combo"),
    ("Sunnhemp", "Sunn Hemp", "MERGED", "spacing variant of the same species (Crotalaria juncea)"),
    ("Rye+Hairy Vetch", "Rye + Hairy Vetch", "MERGED", "spacing around separator only"),
    ("cereal rye & hairy vetch", "Ceral Rye + Hairy Vetch", "MERGED", "case + separator + typo, same combo"),
    ("50%Crimson clover + 50%Ryegrass", "25%Crimson clover + 75%Ryegrass", "KEPT_SEPARATE", "different mixture proportions = different treatment"),
    ("75%Crimson clover + 25%Ryegrass", "50%Crimson clover + 50%Ryegrass", "KEPT_SEPARATE", "different mixture proportions = different treatment"),
    ("75%Crimson clover + 25%Ryegrass", "25%Crimson clover + 75%Ryegrass", "KEPT_SEPARATE", "inverse proportions = different treatment"),
    ("6 species mixture", "12 species mixture", "KEPT_SEPARATE", "different species counts = different treatment"),
    ("Cereal Rye/Hairy Vetch", "cereal rye & hairy vetch", "MERGED", "separator + case only, same combo"),
    ("Cereal Rye/Crimon Clover", "cereal rye & crimson clover", "MERGED", "typo (Crimon->Crimson) + separator + case, same combo"),
    ("Oilseed radish & Rye", "Oilseed radish+Rye", "MERGED", "separator/spacing only, same combo"),
    ("cereal rye & hairy vetch", "Ceral Rye + Hariy Vetch", "MERGED", "same combo as above chain"),
    ("Cereal Rye/Hairy Vetch", "Ceral Rye + Hairy Vetch", "MERGED", "same combo, separator + typo"),
    ("Oilseed Radish", "Oilseed radish+Rye", "KEPT_SEPARATE", "single species vs. a 2-species mixture -- genuinely different treatments"),
    ("white clover + ryegrass", "red clover + ryegrass", "KEPT_SEPARATE", "white clover and red clover are different species"),
    ("Winter Rye", "Winter Rape", "KEPT_SEPARATE", "different species entirely (rye vs. rapeseed); only shares the 'Winter ' prefix and word length"),
    ("Ceral Rye + Hairy Vetch", "Rye + Hairy Vetch", "KEPT_SEPARATE", "is 'Rye' here shorthand for cereal rye, or a genuinely distinct label? Table already tracks 'Rye' (143 rows) and 'Cereal Rye' (28 rows) as separate entries elsewhere -- CONFIRMED by Yu Peng 2026-09-11: kept separate."),
    ("Pea & Canola", "pea and canola", "MERGED", "case + connector word only, same combo"),
    ("Hairy Vetch", "Rye+Hairy Vetch", "KEPT_SEPARATE", "single species vs. a 2-species mixture"),
    ("Cereal Rye/Hairy Vetch", "Ceral Rye + Hariy Vetch", "MERGED", "same combo, separator + typos"),
    ("Mustard & Vetch", "Mustard & Vetch & Rye", "KEPT_SEPARATE", "2-species vs. 3-species mixture"),
    ("winter rye & hairy vetch", "cereal rye & hairy vetch", "KEPT_SEPARATE", "same 'Rye' vs. 'Cereal Rye' vs. 'Winter Rye' question as above -- CONFIRMED by Yu Peng 2026-09-11: kept separate."),
    ("pea and canola", "pea, oat, and canola", "KEPT_SEPARATE", "2-species vs. 3-species mixture (missing oat)"),
    ("Oilseed Radish", "Oilseed radish & Rye", "KEPT_SEPARATE", "single species vs. a 2-species mixture"),
]

dec_df = pd.DataFrame(DECISIONS, columns=["entry_a", "entry_b", "decision", "reasoning"])
dec_df.to_csv(OUT_DIR / "species_merge_decisions.csv", index=False)

# --- YieldTable.xlsx data issues found (not modified in the source file) ---
yld = pd.read_excel(YIELD_XLSX, sheet_name="Yield Record")
cereal_rye_issue = yld[(yld["CCs Species"] == "Cereal Rye") & (yld["CCs Famaily"] == "Legume")]
issue_rows = []
for _, r in cereal_rye_issue.iterrows():
    issue_rows.append({
        "issue_type": "Cereal Rye mislabeled Legume",
        "sheet": "Yield Record",
        "row_id_col1": r["ID-1"],
        "data_source": r["Data Source"],
        "paper_id": r["Paper ID"],
        "article_title": r["Article Title"],
        "current_value": "CCs Famaily = Legume",
        "should_be": "Non-legume (confirmed 2026-09-11)",
    })
issue_rows.append({
    "issue_type": "Phacelia family mistag",
    "sheet": "Yield Record",
    "row_id_col1": "(all rows where CCs Species = Phacelia)",
    "data_source": "", "paper_id": "", "article_title": "",
    "current_value": "Unnamed: 12 (family) = Brassicaceae",
    "should_be": "Boraginaceae (Phacelia is not a Brassica)",
})
pd.DataFrame(issue_rows).to_csv(OUT_DIR / "yieldtable_data_issues_for_review.csv", index=False)

print(f"species_merge_decisions.csv: {len(dec_df)} pairs "
      f"({(dec_df.decision=='MERGED').sum()} merged, "
      f"{(dec_df.decision=='KEPT_SEPARATE').sum()} kept separate, "
      f"{(dec_df.decision=='OPEN_REVIEW').sum()} open review)")
print(f"yieldtable_data_issues_for_review.csv: {len(issue_rows)} issues "
      f"({len(cereal_rye_issue)} Cereal Rye rows + 1 Phacelia note)")
