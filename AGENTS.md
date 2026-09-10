# AGENTS.md

## Repository Purpose

Template for extracting standardized spatial, temporal, and practice
information — plus whichever ecosystem-service response data (yield,
GHG, SOC, nitrogen) a paper reports — from cover crop literature PDFs
into one wide, schema-conformant table.

See **TASKS.md** for a plain-English, tool-agnostic description of the
extraction pipeline. See **schema/cover_crop_schema.yml** for the exact
target field list — read it before writing any extraction code.

This repo is PDF-in. It does not search the web, resolve DOIs from a
citation, or fetch papers on its own. The user supplies a PDF; if a PDF
cannot be read, stop and say so — do not try to locate the paper another
way.

---

## Step 1: Read the Example and the Schema

Read `examples/book4_reference/README.md` before writing a new workflow
— it shows the target output shape using already-verified data. Read
`schema/cover_crop_schema.yml` in full; it is the contract for every
column name, type, extraction method, and status you will produce.

Follow the same pattern as the example: construct a `PaperSpec` for the
input PDF, build an `ExtractionWorkflow`, call `run_extraction()`.

---

## Core Steps

1. **Check the PDF is readable** — `python scripts/check_pdf.py <path>`. If it
   has no text layer (scanned image only) or fails to open, stop and tell
   the user; do not silently fall back to guessing from the filename or
   abstract alone.
2. **Convert to markdown** — `pdf_to_markdown()` in
   `src/literature_extractor.py`. Also attempt lightweight identification
   (DOI regex on the first page, PDF metadata title/author fields) — this
   is a best-effort read of what's printed on the page, never an external
   search. If nothing is found, leave `doi` / `article_title` blank rather
   than guessing.
3. **Locate sections** — `locate_sections()`. Regex-match markdown headers
   for Methods/Study Site/Experimental Design variants and Results
   variants (see the header-pattern list in TASKS.md). Methods → Block 1
   fields (site, design, practice). Results → Block 2 fields (response
   data). If no Methods heading is found, fall back to the Abstract; if
   that's insufficient too, scan the full text but cap confidence at
   `low` for any field found this way (full-text scanning has a higher
   false-positive rate — e.g. picking up a coordinate cited from a
   different study in the Discussion section).
4. **Deterministic extraction (Block 1)** — `extract_deterministic()`.
   Regex/gazetteer only, zero LLM tokens. Covers every schema field with
   `extraction_method: regex` or `gazetteer`. Do not re-ask the LLM for a
   field this step already filled.
5. **Classify response type** — `classify_response_type()`. One cheap LLM
   call reading the Abstract + Results headers/captions. Output populates
   `response_types_detected` (e.g. `"yield,ghg_n2o"`) and determines which
   Block 2 sub-blocks (`yield_data`, `ghg_data`, `soc_data`,
   `nitrogen_data`) to even attempt. A paper can hit more than one
   sub-block — do not assume exclusivity.
6. **Narrow LLM extraction** — `extract_narrow_llm()`. One consolidated
   call per paper, scoped ONLY to the section text located in step 3 —
   never the full paper. Covers every field with `extraction_method:
   narrow_llm` that step 4 didn't already fill, split by section: Methods
   text → Block 1 narrow fields, Results text → the Block 2 sub-blocks
   named in `response_types_detected`.
7. **Vision extraction, only if needed** — `extract_vision_llm()`. Trigger
   ONLY when a Results value is explicitly referenced as being in a
   figure (e.g. "as shown in Fig. 3") and step 6 did not find it in text.
   Render the specific PDF page to an image (code, no LLM) and pass only
   that image to a vision-capable call. **Rule: any field filled this way
   is capped at `medium` confidence, never `high`, unless the figure
   prints an explicit numeric data label** — chart-reading is an
   estimate, not a measurement.
8. **Normalize** — `normalize_fields()`. For every `_raw` field with a
   paired `_norm` field in the schema, apply the controlled-vocabulary
   mapping. Rule-based first; fall back to a narrow LLM call only for
   raw text the rule table doesn't cover. Never skip straight from raw
   text to a "guessed" norm value without going through this step.
9. **Compute response ratios** — `compute_response_ratios()`. Pure math,
   no LLM: for every Block 2 sub-block with both a `cc_mean` and
   `control_mean`, compute `{prefix}ln_response_ratio` and
   `{prefix}var_lnr` (or `{prefix}var_lnr_uniformed` /
   `_harmonic_n` / `_all_ave` for the legacy yield fields — see schema
   comments). Never let an LLM produce these values directly.
10. **Validate** — `validate_with_apis()`. Species names against
    GBIF/WFO, coordinates reverse-geocoded against the stated country via
    GeoNames/Nominatim, numeric sanity ranges. **These API domains are
    not reachable from a sandboxed chat container — this step only runs
    for real on an environment with open network access (e.g. CyVerse).**
    When step 4's regex value and step 6's LLM value disagree on the same
    field, do not silently prefer one — flag for human review.
11. **Confidence-tag and assemble the row** — `assemble_row()`. Every
    extracted field gets a `high` / `medium` / `low` confidence and a
    one-line source note, same convention as the prior Book4.xlsx
    year-extraction pass: `high` = deterministic match or a verbatim
    figure/quote in text; `medium` = inferred from a stated range or
    (per step 7) read from a figure; `low` = full-text fallback,
    publication-year-minus-lag, or any other estimate. A field the
    pipeline cannot fill after all of the above stays blank — never
    fabricate a value to complete a row.
12. **Write output and log** — `run_extraction()` appends the row to
    `workflows/<project_name>/output/`, then **append to
    `PROMPT_ACTION_LOG.md`** — date, user's exact prompt, model name,
    files inspected, actions taken, verification performed, and any
    papers or fields flagged for human review. See the log's own format
    notes for the entry template.

---

## Directory Structure

```
schema/                              Target field list (read first, every time)
  cover_crop_schema.yml
data_catalog.yml                     Cover crop species gazetteer + external validation API registry
src/                                 Core extraction library (read-only)
  literature_extractor.py
scripts/                             Pre-flight helper scripts
  check_pdf.py
  check_urls.py
  find_species.py
examples/book4_reference/            Reference example (read-only) — target output shape
workflows/<project_name>/            Each extraction run gets its own folder
  <script>.py
  output/                            Generated table(s), append-only
docs/                                Not yet built for this project — see README for status
```

---

## Required Script Header

Every workflow script must include this before importing from `src/`:

```python
import sys
from pathlib import Path

_repo_root = next(p for p in Path(__file__).resolve().parents
                  if (p / "src" / "literature_extractor.py").exists())
sys.path.insert(0, str(_repo_root))

from src.literature_extractor import (
    PaperSpec,
    ExtractionWorkflow,
    run_extraction,
)
```

---

## Batch Runs

For more than a handful of PDFs, run in the background and poll rather
than blocking:

```bash
mkdir -p workflows/<project_name>/output
nohup python workflows/<project_name>/<script>.py > workflows/<project_name>/output/run.log 2>&1 &
```

Poll `.status` (first at 2 min, then every 3 min). Wait for completion
before re-running. One failed paper must never halt the batch — log the
failure against that paper, continue to the next.

---

## Output Requirements

- One row per treatment comparison, appended to
  `workflows/<project_name>/output/<name>.csv` (or `.xlsx` if the user
  asked for Excel), columns exactly matching `schema/cover_crop_schema.yml`
  in field order.
- Every extracted (non-`computed_downstream`) field gets a matching
  `<field>_confidence` and `<field>_source` pair — see step 11.
- Fields marked `status: dropped` or `status: needs_confirmation` in the
  schema are never populated. Fields marked `proposed_new` are only
  populated once the user has confirmed them (see the schema's
  `open_questions` list) — do not silently start filling them.

---

## Failure Handling

- PDF unreadable (no text layer, corrupted) → stop, tell the user which
  file and why, do not attempt vision-only reading of the whole document
  as a substitute for normal extraction.
- No Methods section found by heading match or Abstract fallback → flag
  low confidence on every Block 1 field for that paper, do not guess
  values to fill the gap.
- Regex value and narrow-LLM value disagree on the same field → flag for
  human review, do not average or arbitrarily pick one.
- A Results value is claimed to be figure-only but the referenced figure
  page can't be rendered or located → leave the field blank, do not
  estimate from surrounding text.

---

## Confidence Rules (see also step 11)

- `high` — deterministic regex/gazetteer match, or an LLM extraction
  quoting an exact number/phrase found verbatim in text.
- `medium` — LLM extraction requiring inference from a stated range or
  description, OR any `vision_llm`-sourced value (see step 7).
- `low` — full-text fallback scan, publication-year-minus-lag estimate,
  or any other last-resort method.

## Ad-Hoc Preprocessing

`pdftotext`, `pdfimages`, and `pdftoppm` (poppler-utils) are available
for PDF inspection or page-to-image rendering ahead of a vision call.
