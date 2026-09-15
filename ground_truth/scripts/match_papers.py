"""
Cross-match papers between the two hand-digitized ground-truth tables
(YieldTable.xlsx, GHGTable.xlsx) so both can be used as one gold-answer
set keyed to the same paper.

Why this is needed: neither table shares a clean primary key.
  - GHGTable identifies a paper by a full citation string (`reference`)
    plus a sparsely-filled `doi`.
  - YieldTable identifies a paper by `Article Title` (clean) and
    `Paper ID` (unreliable: entirely null for "Dataset One", and null
    for 9/736 rows of "Dataset Two").

Matching strategy (title-in-citation containment, not generic fuzzy
scoring): a citation string is expected to literally contain the paper
title as a substring, so we normalize both sides (lowercase, strip
punctuation/whitespace) and test containment first; substring matching
on real citation text is far more reliable here than a similarity
score, and produces fewer false positives. Only when containment fails
do we fall back to difflib's SequenceMatcher ratio, and anything below
the threshold is left for manual review rather than guessed.

Output: ground_truth/output/paper_matching.csv, one row per unique
YieldTable Article Title, with whatever GHGTable reference (if any) it
was matched to. A yield paper with no GHG match is not necessarily an
error -- it may simply be a yield-only paper.
"""
import re
import difflib
from pathlib import Path

import pandas as pd

import os

# Real path on Yu Peng's machine (OneDrive-synced "CC maps" project folder).
# Override with env vars when running through a mounted/aliased path instead.
# GHG.xlsx's "Deduplicated" sheet is the authoritative GHG ground truth
# (confirmed 2026-09-11); it has a clean paper_id + paper_citation_APA,
# unlike the superseded GHGTable.xlsx.
_DEFAULT_DIR = str(Path(__file__).resolve().parents[1] / "source_data")  # ground_truth/source_data/ -- committed to git (2026-09-15), see ground_truth/README.md
GHG_XLSX = Path(os.environ.get("GHG_XLSX_PATH", f"{_DEFAULT_DIR}/GHG.xlsx"))
YIELD_XLSX = Path(os.environ.get("YIELD_XLSX_PATH", f"{_DEFAULT_DIR}/YieldTable.xlsx"))
OUT_CSV = Path(__file__).resolve().parents[1] / "output" / "paper_matching.csv"

FUZZY_THRESHOLD = 0.55  # below this, we report "no match" rather than a weak guess


def normalize(text: str) -> str:
    text = str(text).lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def main() -> None:
    ghg = pd.read_excel(GHG_XLSX, sheet_name="Deduplicated")
    yld = pd.read_excel(YIELD_XLSX, sheet_name="Yield Record")

    ghg_papers = (
        ghg[["paper_id", "paper_citation_APA", "paper_doi"]]
        .rename(columns={"paper_citation_APA": "reference", "paper_doi": "doi"})
        .drop_duplicates(subset=["paper_id"])
        .reset_index(drop=True)
    )
    ghg_papers["norm_reference"] = ghg_papers["reference"].map(normalize)

    yld_papers = (
        yld[["Article Title", "Paper ID", "Data Source"]]
        .drop_duplicates(subset=["Article Title"])
        .reset_index(drop=True)
    )
    yld_papers["norm_title"] = yld_papers["Article Title"].map(normalize)

    rows = []
    for _, yrow in yld_papers.iterrows():
        title_norm = yrow["norm_title"]
        match_method = "none"
        matched_ref = None
        matched_doi = None
        matched_paper_id = None
        score = 0.0

        # 1. substring containment (title should appear verbatim inside the citation)
        contains = ghg_papers[ghg_papers["norm_reference"].str.contains(
            re.escape(title_norm), na=False
        )]
        if len(contains) == 1:
            matched_ref = contains.iloc[0]["reference"]
            matched_doi = contains.iloc[0]["doi"]
            matched_paper_id = contains.iloc[0]["paper_id"]
            match_method = "substring"
            score = 1.0
        elif len(contains) > 1:
            matched_ref = " | ".join(contains["reference"].tolist())
            matched_paper_id = " | ".join(str(x) for x in contains["paper_id"].tolist())
            match_method = "substring_multiple_AMBIGUOUS"
            score = 1.0
        else:
            # 2. fuzzy fallback (handles truncated/rephrased titles in the citation)
            best_ratio = 0.0
            best_ref = None
            best_doi = None
            best_paper_id = None
            for _, grow in ghg_papers.iterrows():
                ratio = difflib.SequenceMatcher(None, title_norm, grow["norm_reference"]).ratio()
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_ref = grow["reference"]
                    best_doi = grow["doi"]
                    best_paper_id = grow["paper_id"]
            if best_ratio >= FUZZY_THRESHOLD:
                matched_ref = best_ref
                matched_doi = best_doi
                matched_paper_id = best_paper_id
                match_method = "fuzzy_REVIEW"
                score = round(best_ratio, 3)
            else:
                match_method = "no_match_in_GHG_table"
                score = round(best_ratio, 3)

        rows.append({
            "yield_article_title": yrow["Article Title"],
            "yield_paper_id": yrow["Paper ID"],
            "yield_data_source": yrow["Data Source"],
            "match_method": match_method,
            "match_score": score,
            "matched_ghg_paper_id": matched_paper_id,
            "matched_ghg_reference": matched_ref,
            "matched_ghg_doi": matched_doi,
        })

    out = pd.DataFrame(rows)
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT_CSV, index=False)

    print(f"Yield papers total: {len(out)}")
    print(out["match_method"].value_counts())
    print(f"\nWritten to {OUT_CSV}")


if __name__ == "__main__":
    main()
