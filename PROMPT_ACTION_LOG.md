# Prompt Action Log

Append-only. One entry per extraction run — see AGENTS.md step 12.

Entry format:

```
## YYYY-MM-DD

### Prompt
<the user's exact request>

### LLM
<model name/version used>

### Files and folders inspected
- <paths>

### Actions taken
- <what was extracted, from which PDFs, into which workflow output>

### Verification
- <what was checked — confidence breakdown, any GBIF/WFO/GeoNames validation run>

### Flagged for human review
- <papers/fields flagged, and why — see AGENTS.md Failure Handling>

### Open questions and follow-up
- <anything left unresolved>
```

---

(No entries yet — this repo was just scaffolded from LLM_lesson_exemplar.)

## 2026-09-10

### Prompt
端到端测试 Franco et al. 2021 论文的提取流程

### LLM
claude-sonnet-4-6 via https://llm-api.cyverse.ai/v1 — 0 call(s), 0 prompt / 0 completion tokens

### Files and folders inspected
- test_pdfs/franco2021.pdf

### Actions taken
- `workflows/run_extraction.py --project franco2021_test` → 0 row(s) written to `/home/jovyan/data-store/LLM_AutoExtracting_CC/workflows/franco2021_test/output/franco2021_test.csv`
- per-paper report: `/home/jovyan/data-store/LLM_AutoExtracting_CC/workflows/franco2021_test/output/franco2021_test_report.json`

### Verification
- offline sanity_check_row() flags are in the `review_flags` column; response ratios recomputed in code
- external API validation (GBIF/WFO/GeoNames): not run (validate_with_apis not yet wired)

### Flagged for human review
- franco2021.pdf: failed — RuntimeError('LLM call \'classify_response_type\' failed after 3 attempts: PermissionDeniedError(\'Error code: 403 - {\\\'error\\\': {\\\'message\\\': "team not allowed to access model. This team can only access models=[\\\'esiil\\\', \\\'js2\\\', \\\'cyverse\\\', \\\'nrp\\\']. Tried to access claude-sonnet-4-6", \\\'type\\\': \\\'team_model_access_denied\\\', \\\'param\\\': \\\'model\\\', \\\'code\\\': \\\'403\\\'}}\')')

### Open questions and follow-up
- review every `low` / `medium` confidence cell against the PDF before merging into the master table

## 2026-09-10

### Prompt
端到端测试 Franco et al. 2021 论文的提取流程

### LLM
js2/gpt-oss-120b via https://llm-api.cyverse.ai/v1 — 5 call(s), 18117 prompt / 3974 completion tokens

### Files and folders inspected
- test_pdfs/franco2021.pdf

### Actions taken
- `workflows/run_extraction.py --project franco2021_test` → 1 row(s) written to `/home/jovyan/data-store/LLM_AutoExtracting_CC/workflows/franco2021_test/output/franco2021_test.csv`
- per-paper report: `/home/jovyan/data-store/LLM_AutoExtracting_CC/workflows/franco2021_test/output/franco2021_test_report.json`

### Verification
- offline sanity_check_row() flags are in the `review_flags` column; response ratios recomputed in code
- external API validation (GBIF/WFO/GeoNames): not run (validate_with_apis not yet wired)

### Flagged for human review
- franco2021.pdf: ok — no supported response type detected — Block 2 left blank

### Open questions and follow-up
- review every `low` / `medium` confidence cell against the PDF before merging into the master table

## 2026-09-10

### Prompt
test run on franco2021.pdf

### LLM
js2/gpt-oss-120b via https://llm-api.cyverse.ai/v1 — 5 call(s), 18117 prompt / 3753 completion tokens

### Files and folders inspected
- test_pdfs/franco2021.pdf

### Actions taken
- `workflows/run_extraction.py --project franco2021_test` → 1 row(s) written to `/home/jovyan/data-store/LLM_AutoExtracting_CC/workflows/franco2021_test/output/franco2021_test.csv`
- per-paper report: `/home/jovyan/data-store/LLM_AutoExtracting_CC/workflows/franco2021_test/output/franco2021_test_report.json`

### Verification
- offline sanity_check_row() flags are in the `review_flags` column; response ratios recomputed in code
- external API validation (GBIF/WFO/GeoNames): not run (validate_with_apis not yet wired)

### Flagged for human review
- franco2021.pdf: ok — no supported response type detected — Block 2 left blank

### Open questions and follow-up
- review every `low` / `medium` confidence cell against the PDF before merging into the master table
