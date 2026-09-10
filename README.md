# Cover Crop Literature Extraction

Extracts standardized spatial, temporal, and practice information — plus
whichever ecosystem-service response data (yield, GHG, SOC, nitrogen) a
paper reports — from cover crop research PDFs into one wide,
schema-conformant table.

This is an **agentic repository**: the repo, not a chat conversation, is
the unit of work. `AGENTS.md` defines exactly how an AI agent (or a
person) is allowed to operate within it — see
[Agents and Systems](#design-philosophy) below. Forked from
[CU-ESIIL/LLM_lesson_exemplar](https://github.com/CU-ESIIL/LLM_lesson_exemplar),
replacing its geospatial-raster-harmonization domain logic with
literature-extraction logic; the repository *pattern* (AGENTS.md,
TASKS.md, examples/ vs workflows/, the required script header, the
nohup+poll batch pattern) is unchanged.

---

## What this repository does

Given one PDF:

1. Converts it to Markdown, locates the Methods and Results sections.
2. Pulls Block 1 (core plot/practice info — location, cover crop
   species, cash crop, timeline) via regex/gazetteer first, LLM only
   for what code can't get.
3. Classifies which ecosystem-service response types (yield / GHG / SOC
   / nitrogen) the paper reports, then pulls those Block 2 fields from
   Results text, tables, or — only when explicitly figure-referenced —
   a vision read of the rendered chart.
4. Normalizes messy raw text into controlled-vocabulary fields
   (`_raw`/`_norm` pairs), computes response ratios by pure math.
5. Validates species names and coordinates against external APIs
   (GBIF / WFO / GeoNames).
6. Tags every field `high` / `medium` / `low` confidence with a source
   note, and writes one row to the output table. Never fabricates a
   value it couldn't find.

Full step-by-step logic: [TASKS.md](TASKS.md). Agent operating rules:
[AGENTS.md](AGENTS.md). Target field list:
[schema/cover_crop_schema.yml](schema/cover_crop_schema.yml).

---

## Quick Start

Install dependencies:

```bash
pip install -r requirements.txt
```

Check a PDF is readable before running anything on it:

```bash
python scripts/check_pdf.py path/to/paper.pdf
```

Look up a cover crop species in the gazetteer:

```bash
python scripts/find_species.py vetch
```

Read `examples/book4_reference/README.md` for the target output shape,
then start a new run under `workflows/<project_name>/` following
AGENTS.md's Required Script Header.

---

## Repository Structure

```text
schema/
  cover_crop_schema.yml           # target field list — read before writing any extraction code

data_catalog.yml                  # cover crop species gazetteer + external validation API registry

src/
  literature_extractor.py         # core extraction library — import from here, don't modify

examples/
  book4_reference/                 # reference example — learn from here, don't modify
    README.md
    expected_output.csv

workflows/                         # your extraction runs go here
  my_project/                      # one folder per run
    my_script.py
    output/                        # generated table(s)

scripts/                           # pre-flight helpers
  check_pdf.py
  check_urls.py
  find_species.py

tests/                              # pytest — library import/schema/pure-code-stage checks
AGENTS.md                           # LLM behavior and workflow rules
TASKS.md                            # tool-agnostic pipeline description
PROMPT_ACTION_LOG.md                # append-only record of every extraction run
requirements.txt
```

**If you are a scientist using this as a template:**
- Read `examples/book4_reference/README.md` to understand the target shape
- Create a new folder in `workflows/` for each extraction project
- Outputs land in your project's own `output/` folder, next to the script

**If you are an LLM agent:**
- New runs go in `workflows/<project_name>/`, not in `examples/`
- Core library is `src/literature_extractor.py` — read it before writing extraction code
- Full rules are in `AGENTS.md`

---

## Python API

```python
from pathlib import Path
from src.literature_extractor import PaperSpec, ExtractionWorkflow, run_extraction

workflow = ExtractionWorkflow(
    name="my_run",
    papers=[PaperSpec(pdf_path=Path("path/to/paper.pdf"), paper_id=1)],
    output_dir=Path("workflows/my_project/output"),
    verbose=True,
)

rows = run_extraction(workflow)
```

Note: `run_extraction` performs the pure-code stages (PDF readability
check, markdown conversion, section location, deterministic
regex/gazetteer extraction, normalization, response-ratio computation,
row assembly). The LLM-calling stages (`classify_response_type`,
`extract_narrow_llm`, `extract_vision_llm`) and the API-validation stage
(`validate_with_apis`) are stubs in `src/literature_extractor.py` — wire
them to your model provider in your own workflow script. See AGENTS.md
step-by-step for exactly where each one plugs in.

---

## Design Philosophy

- The LLM handles judgment calls: classifying what a paper reports,
  reading free text that needs interpretation, reading a figure when
  there's no alternative.
- Deterministic code handles everything it can: PDF conversion, section
  location, coordinate/species/tillage matching, normalization rules,
  response-ratio math, external API validation.
- Every extracted value carries its confidence and evidence — nothing
  is asserted without a traceable source.
- The repository, not a chat transcript, is the reusable artifact. See
  `docs/agents-and-systems.md` in the upstream
  [LLM_lesson_exemplar](https://github.com/CU-ESIIL/LLM_lesson_exemplar)
  template for the fuller argument — this repo follows that same
  agentic-repository pattern; its own documentation site is not yet
  built (see Status below).

---

## Status

- Schema: confirmed (`schema/cover_crop_schema.yml`, v0.4). A few fields
  are marked `proposed_new` or `needs_confirmation` — see the schema's
  `open_questions` list before extending the pipeline to cover them.
- Pure-code pipeline stages: implemented and tested (`tests/test_import.py`).
- LLM/vision/API stages: stubbed, intentionally — wire to a model
  provider per AGENTS.md before running on real papers.
- Documentation site (mkdocs, as in the upstream template): not yet
  built for this project.
- Deployment: prototyped in a chat sandbox (no external network access
  to GBIF/WFO/GeoNames from there); intended for production runs on
  CyVerse, where those APIs are reachable.

---

## Notes

This repository is derived from a teaching/demonstration template
([CU-ESIIL/LLM_lesson_exemplar](https://github.com/CU-ESIIL/LLM_lesson_exemplar))
and adapted for a real research use case: building a reusable dataset of
where, when, and how cover crops are used, and what ecosystem-service
outcomes the literature reports.
