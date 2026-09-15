# Ground truth: sources, tiering, and derived tables

## Source files (`ground_truth/source_data/` — committed to git, 2026-09-15)

These used to live only on OneDrive at a hardcoded per-machine path,
which broke every time OneDrive hadn't fully synced/hydrated the file
locally (Files On-Demand placeholder) or on a different machine
entirely. Per Yu Peng (2026-09-15), copied into the repo instead — this
repo is private, and these are Yu Peng's own curated spreadsheets, not
copyrighted third-party material (unlike `ground_truth/pdfs/`, which
stays gitignored for exactly that reason). All scripts still honor
`GHG_XLSX_PATH` / `YIELD_XLSX_PATH` env var overrides if you ever need
to point at a different copy.

- **YieldTable.xlsx** ("Yield Record" sheet) — 1026 rows, 91 papers
  (Dataset One: 290 rows / 28 papers, no `Paper ID`; Dataset Two: 736
  rows / 61 papers, `Paper ID` populated for all but 9 rows).
- **GHG.xlsx** ("Deduplicated" sheet) — **the authoritative GHG ground
  truth**, 489 rows, 112 papers, clean `paper_id` for every row.
  Confirmed 2026-09-11: **GHGTable.xlsx is deprecated** — do not read
  from it in any script or eval going forward (also why it was NOT
  copied into `source_data/` alongside the two files above — no script
  reads it, so there was nothing to fix a path for). GHG.xlsx's other
  sheets (Sheet1, Prior MetaData Cleaning Record, Prior Meta Paper
  List, Original Meta, Dictionary, Sheet2, Sheet3) are process/audit
  trail that feeds "Deduplicated" — never a data source on their own.

**No paper overlaps between YieldTable and GHG.xlsx** — confirmed by
`match_papers.py` (0/91 matches, using a clean `paper_id` key on the
GHG side). These are two independently built literature sets; a paper
appearing in one table says nothing about whether it appears in the
other.

## Trust tiers (confirmed 2026-09-11)

GHG.xlsx's "Deduplicated" sheet mixes data from 4 prior published
meta-analyses (`study_source` 1–4: Stafni / Han / Li / Qiu et al.) with
a fresh WoS search of this project's own (`study_source` 5). Only the
52 rows flagged `manul checked & revised == "y"` have been personally
checked by Yu Peng against the original paper.

- **Tier 1 — `ghg_gold_tier1_manually_verified.csv`**: 52 rows / 18
  papers. Highest-trust gold subset — use this to seed and prioritize
  the extraction-agent eval harness.
- **Tier 2 — `ghg_gold_tier2_reference_only.csv`**: 437 rows / 105
  papers (404 reused from prior meta-analyses, 33 from this project's
  own WoS search, not independently re-verified here). Useful
  reference, weight lower than Tier 1 when scoring pipeline accuracy.

YieldTable.xlsx has no equivalent verification flag — treat it as one
undifferentiated tier unless/until Yu Peng flags a subset the same way.

## GHG gold eval table (schema-aligned, ready for scoring)

`build_gold_eval_ghg_table.py` melts GHG.xlsx Deduplicated's wide
co2/n2o/ch4 columns into this repo's long-format schema (one row = one
gas), renaming columns onto real schema field names where a same-meaning
field exists (`country`, `tillage_type_raw`, `cc_planting_time_raw`,
`cc_terminating_time_raw`, `cc_category`, `cc_duration_years`, ...) and
keeping everything else under an `extra__` prefix rather than dropping
it. `cc_duration_years` <- `CC.duration` confirmed by Yu Peng
(2026-09-12): "the total number of years cover crop was used." Output:
`gold_eval_ghg_tier1.csv` (65 rows from the 52 Tier-1 source rows) and
`gold_eval_ghg_tier2.csv` (606 rows from the 437 Tier-2 source rows).

## Species normalization table (4-tier scheme)

`species_normalization_table.csv` — 146 canonical entries, built from
YieldTable's `CCs Species`/`Unnamed: 12`/`CCs Famaily` and GHG.xlsx
Deduplicated's `CC_species`/`CC_types`.

- Tier 1 (verbatim original wording per paper) is **not** built here —
  neither source table records the paper's exact original phrase, only
  an already-normalized common name. Tier 1 can only come from a fresh
  LLM read of each paper's own text.
- Tier 2 (common name) = `tier2_common_name`.
- Tier 3 (family) = `tier3_family` — **on hold, per Yu Peng's call
  2026-09-11 ("not for now")**. GBIF/WFO lookup is not reachable from
  either this device's shell or the cloud sandbox (org egress policy
  blocks `api.gbif.org` / `worldfloraonline.org`); a fallback fill
  (legume-rule + a fixed botanical-knowledge dictionary) was drafted in
  `finalize_species_table.py` but is disabled (`FILL_TIER3_FAMILY =
  False`) rather than used, since it wasn't a real lookup. Every entry
  currently reads `NEEDS_CONFIRMATION`; revisit once a real GBIF/WFO
  path (or another source) is available.
- Tier 4 (functional group) = `tier4_functional_group`
  (legume/non-legume/mixture/rotation).

Confirmed corrections applied (2026-09-11):
- **Cereal Rye → Non-legume** (was inconsistent: 24/25 YieldTable rows
  said Legume, 1 said Non-legume, in disagreement with GHG.xlsx's own 3
  Cereal Rye rows, all Non-legume). The 24 mislabeled source rows are
  listed, not silently fixed, in `yieldtable_data_issues_for_review.csv`.
- **Phacelia's family corrected Brassicaceae → Boraginaceae** (the
  source `Unnamed: 12` column mistags it) — also listed in that file.

`species_merge_decisions.csv` documents all 24 near-duplicate spelling
pairs originally flagged: 11 merged as typo/formatting variants, 13
kept separate (11 genuinely different treatments/species, plus 2
resolved 2026-09-11 by Yu Peng — "Rye"/"Cereal Rye"/"Winter Rye" stay as
distinct entries, matching the existing table's own convention of
tracking them separately elsewhere).

## Scripts (run in this order to rebuild everything)

```bash
python ground_truth/scripts/match_papers.py
python ground_truth/scripts/build_species_table.py
python ground_truth/scripts/finalize_species_table.py
python ground_truth/scripts/build_review_files.py
python ground_truth/scripts/extract_gold_tier1.py
```

Each defaults to reading from `ground_truth/source_data/` (committed to
git); pass `GHG_XLSX_PATH` / `YIELD_XLSX_PATH` env vars to point at a
different copy instead.

## Output files

| File | What it is |
|---|---|
| `paper_matching.csv` | Every YieldTable paper, best GHG.xlsx match attempt (none found — see above) |
| `species_normalization_table.csv` | Final 4-tier species table (tiers 2–4) |
| `species_merge_log.csv` | Which raw entries got auto-collapsed into which canonical spelling |
| `species_merge_decisions.csv` | All 24 near-duplicate pairs + decision + reasoning, for review |
| `species_open_review_notes.txt` | The Rye/Cereal Rye/Winter Rye open question |
| `yieldtable_data_issues_for_review.csv` | Source-data problems found, not auto-fixed in the spreadsheet |
| `ghg_gold_tier1_manually_verified.csv` | 52-row Tier 1 gold subset |
| `ghg_gold_tier2_reference_only.csv` | 437-row Tier 2 reference subset |
