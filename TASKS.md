# Cover Crop Literature Extraction Tasks

This document describes the steps needed to extract standardized data
from a cover crop research PDF into the schema defined in
`schema/cover_crop_schema.yml`. It is tool-agnostic — the same pipeline
applies whether implemented in Python, R, or any other stack.

---

## Input

- A single PDF file (the pipeline does not search for or fetch papers —
  see AGENTS.md).

## Output

- One or more rows (one per treatment comparison) appended to a table
  matching `schema/cover_crop_schema.yml`, each field carrying a
  confidence (`high` / `medium` / `low`) and a one-line source note.

---

## Task 1: Verify the PDF Is Readable

Open the PDF and confirm it has a text layer (not a scanned image with
no OCR). If it does not, or the file is corrupted, stop and report which
file failed — do not proceed with any other task for this paper.

---

## Task 2: Convert to Markdown and Identify the Paper

Convert the PDF to Markdown, preserving heading structure (this narrows
every later search — do it once, cache the result). Attempt a
best-effort identification pass on the same pass:

- Read PDF metadata fields (title, DOI if embedded).
- Regex-scan the first page for a DOI pattern (`10\.\d{4,9}/\S+`).
- If neither yields anything, leave `doi` / `article_title` blank. Do
  not search the web to resolve them — this pipeline is PDF-in only.

---

## Task 3: Locate the Methods and Results Sections

Scan the Markdown's header structure for section-title variants:

- Methods-like: "Materials and Methods", "Methods", "Materials &
  Methods", "Study Site", "Experimental Design", with or without
  numbering ("2. Materials and Methods", "2.1 Study Site").
- Results-like: "Results", "Results and Discussion".

Take everything from a matched heading to the next top-level heading as
that section's span — do not sub-divide further; over-splitting risks
missing information for near-zero cost savings at this stage.

Fallback order if Methods isn't found: Abstract, then full text (full-
text matches get a `low` confidence cap — higher false-positive risk,
e.g. picking up a coordinate cited from a different study).

---

## Task 4: Extract Block 1 (Core Plot / Practice Info) — Deterministic Pass

From the Methods span, using regex and controlled-vocabulary
(gazetteer) matching only — no LLM call:

- Coordinates (latitude/longitude patterns, DMS or decimal).
- Country (ISO country-name gazetteer).
- Cover crop species (matched against `data_catalog.yml`'s species
  list).
- Tillage (already a clean controlled vocabulary: NT/CT/RT).
- Any other schema field marked `extraction_method: regex` or
  `gazetteer`.

---

## Task 5: Extract Block 1 — Narrow LLM Pass

For the remaining Block 1 fields (marked `extraction_method:
narrow_llm` in the schema and not already filled by Task 4), make one
LLM call scoped to the Methods span only. This covers fields like
planting/termination timing, rotation, fertilization, irrigation,
tillage detail, soil texture — text that needs interpretation, not
pattern matching.

---

## Task 6: Classify Which Response Variables This Paper Reports

Read the Abstract plus the Results section's headers/table/figure
captions. Determine which of the Block 2 sub-blocks apply: yield, GHG
(CO2/N2O/CH4), SOC, nitrogen (and disambiguate which nitrogen metric —
mineral-N-at-sowing, leaching, or total-N). A paper may report more
than one. Record the result in `response_types_detected`. This
determines which Block 2 sub-blocks Tasks 7-8 attempt — do not search
for yield data in a paper classified as GHG-only.

---

## Task 7: Extract Block 2 (Response Data) — Text and Tables

For each sub-block named in Task 6's output, search the Results span
(text and any parsed tables) for: `{prefix}cc_mean`,
`{prefix}control_mean`, `{prefix}cc_sd`, `{prefix}control_sd`,
`{prefix}unit`, `{prefix}n`, and (for multi-year studies) map each
value to a specific `year` using the same value-cross-referencing logic
used for the Book4.xlsx year extraction — if a paper reports two years
of N2O flux, match each numeric value to the year the text or table
associates it with, rather than assigning the whole range to every row.

---

## Task 8: Extract Block 2 — Figure-Only Values

Only when Task 7 doesn't find a needed value in text/tables AND the
paper explicitly points to a figure for it (e.g. "as shown in Fig. 3"):
render that PDF page to an image and read the value with a vision-
capable model call, scoped to that one image. Cap confidence at
`medium` unless the figure prints an explicit numeric label. If the
referenced figure can't be located or rendered, leave the field blank.

---

## Task 9: Normalize

For every field with a `_raw`/`_norm` pair in the schema, produce the
`_norm` value: rule-based controlled-vocabulary mapping first (e.g.
"Yes (pre+post)" → `Yes-pre+post`), falling back to a narrow LLM call
only for text the rule table doesn't cover. Trim/clean simple
inconsistencies (trailing spaces, case) as part of this pass, not
during extraction.

---

## Task 10: Compute Response Ratios

Pure computation, no LLM: for every Block 2 sub-block with both a
`cc_mean` and `control_mean` present, compute the log response ratio
and its variance using the same response-ratio meta-analysis method
already in use for the yield block (see schema comments for the
legacy multi-method variance fields kept for the yield block
specifically).

---

## Task 11: Validate

- Species names against GBIF / World Flora Online.
- Coordinates reverse-geocoded and checked against the stated country
  (GeoNames / Nominatim).
- Numeric sanity ranges (plausible yield magnitudes, year within a
  reasonable bound, coordinates within valid lat/lon ranges).
- Cross-method agreement: where a field was filled by both Task 4
  (deterministic) and independently touched by Task 5/7 (LLM), flag a
  mismatch rather than silently picking one value.

These external API calls require open network access and will not
succeed from a sandboxed environment without it.

---

## Task 12: Assemble the Row and Tag Confidence

Merge every task's output into one row matching the schema exactly.
Every field gets a confidence (`high` / `medium` / `low`) and a short
source note explaining the evidence (verbatim quote location, range
interpreted, or fallback method used). Any field that remains unfilled
after all tasks stays blank — never fabricate a value.

---

## Task 13: Document the Work

Append an entry to `PROMPT_ACTION_LOG.md`:

- The original user request.
- Which PDF(s) were processed.
- Key decisions made (section fallback used, response types classified,
  any vision-extraction triggered).
- Any papers or fields flagged for human review, and why.
