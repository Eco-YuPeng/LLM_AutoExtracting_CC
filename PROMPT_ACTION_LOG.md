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

## 2026-09-14

### Prompt
multimodel gold-eval run: model=js2/gpt-oss-120b, paper_id=2

### LLM
js2/gpt-oss-120b via https://llm-api.cyverse.ai/v1 — 11 call(s), 75387 prompt / 53605 completion tokens

### Files and folders inspected
- /Users/yupe4788/Library/CloudStorage/OneDrive-UCB-O365/Documents/GitHub/LLM_AutoExtracting_CC/ground_truth/pdfs/2_li2015.pdf

### Actions taken
- `workflows/run_extraction.py --project gold_tier1_js2gptoss120b` → 20 row(s) written to `/Users/yupe4788/Library/CloudStorage/OneDrive-UCB-O365/Documents/GitHub/LLM_AutoExtracting_CC/workflows/gold_tier1_js2gptoss120b/output/gold_tier1_js2gptoss120b.csv`
- per-paper report: `/Users/yupe4788/Library/CloudStorage/OneDrive-UCB-O365/Documents/GitHub/LLM_AutoExtracting_CC/workflows/gold_tier1_js2gptoss120b/output/gold_tier1_js2gptoss120b_report.json`

### Verification
- offline sanity_check_row() flags are in the `review_flags` column; response ratios recomputed in code
- external API validation (GBIF/WFO/GeoNames): not run (validate_with_apis not yet wired)

### Flagged for human review
- none

### Open questions and follow-up
- review every `low` / `medium` confidence cell against the PDF before merging into the master table

## 2026-09-14

### Prompt
multimodel gold-eval run: model=js2/gpt-oss-120b, paper_id=6

### LLM
js2/gpt-oss-120b via https://llm-api.cyverse.ai/v1 — 6 call(s), 33814 prompt / 8677 completion tokens

### Files and folders inspected
- /Users/yupe4788/Library/CloudStorage/OneDrive-UCB-O365/Documents/GitHub/LLM_AutoExtracting_CC/ground_truth/pdfs/6_sapkota2017.pdf

### Actions taken
- `workflows/run_extraction.py --project gold_tier1_js2gptoss120b` → 3 row(s) written to `/Users/yupe4788/Library/CloudStorage/OneDrive-UCB-O365/Documents/GitHub/LLM_AutoExtracting_CC/workflows/gold_tier1_js2gptoss120b/output/gold_tier1_js2gptoss120b.csv`
- per-paper report: `/Users/yupe4788/Library/CloudStorage/OneDrive-UCB-O365/Documents/GitHub/LLM_AutoExtracting_CC/workflows/gold_tier1_js2gptoss120b/output/gold_tier1_js2gptoss120b_report.json`

### Verification
- offline sanity_check_row() flags are in the `review_flags` column; response ratios recomputed in code
- external API validation (GBIF/WFO/GeoNames): not run (validate_with_apis not yet wired)

### Flagged for human review
- none

### Open questions and follow-up
- review every `low` / `medium` confidence cell against the PDF before merging into the master table

## 2026-09-14

### Prompt
multimodel gold-eval run: model=js2/gpt-oss-120b, paper_id=10

### LLM
js2/gpt-oss-120b via https://llm-api.cyverse.ai/v1 — 7 call(s), 35100 prompt / 21916 completion tokens

### Files and folders inspected
- /Users/yupe4788/Library/CloudStorage/OneDrive-UCB-O365/Documents/GitHub/LLM_AutoExtracting_CC/ground_truth/pdfs/10_haque2015.pdf

### Actions taken
- `workflows/run_extraction.py --project gold_tier1_js2gptoss120b` → 9 row(s) written to `/Users/yupe4788/Library/CloudStorage/OneDrive-UCB-O365/Documents/GitHub/LLM_AutoExtracting_CC/workflows/gold_tier1_js2gptoss120b/output/gold_tier1_js2gptoss120b.csv`
- per-paper report: `/Users/yupe4788/Library/CloudStorage/OneDrive-UCB-O365/Documents/GitHub/LLM_AutoExtracting_CC/workflows/gold_tier1_js2gptoss120b/output/gold_tier1_js2gptoss120b_report.json`

### Verification
- offline sanity_check_row() flags are in the `review_flags` column; response ratios recomputed in code
- external API validation (GBIF/WFO/GeoNames): not run (validate_with_apis not yet wired)

### Flagged for human review
- none

### Open questions and follow-up
- review every `low` / `medium` confidence cell against the PDF before merging into the master table

## 2026-09-14

### Prompt
multimodel gold-eval run: model=js2/gpt-oss-120b, paper_id=11

### LLM
js2/gpt-oss-120b via https://llm-api.cyverse.ai/v1 — 6 call(s), 26434 prompt / 15630 completion tokens

### Files and folders inspected
- /Users/yupe4788/Library/CloudStorage/OneDrive-UCB-O365/Documents/GitHub/LLM_AutoExtracting_CC/ground_truth/pdfs/11_weiler2018.pdf

### Actions taken
- `workflows/run_extraction.py --project gold_tier1_js2gptoss120b` → 12 row(s) written to `/Users/yupe4788/Library/CloudStorage/OneDrive-UCB-O365/Documents/GitHub/LLM_AutoExtracting_CC/workflows/gold_tier1_js2gptoss120b/output/gold_tier1_js2gptoss120b.csv`
- per-paper report: `/Users/yupe4788/Library/CloudStorage/OneDrive-UCB-O365/Documents/GitHub/LLM_AutoExtracting_CC/workflows/gold_tier1_js2gptoss120b/output/gold_tier1_js2gptoss120b_report.json`

### Verification
- offline sanity_check_row() flags are in the `review_flags` column; response ratios recomputed in code
- external API validation (GBIF/WFO/GeoNames): not run (validate_with_apis not yet wired)

### Flagged for human review
- none

### Open questions and follow-up
- review every `low` / `medium` confidence cell against the PDF before merging into the master table

## 2026-09-14

### Prompt
multimodel gold-eval run: model=js2/gpt-oss-120b, paper_id=14

### LLM
js2/gpt-oss-120b via https://llm-api.cyverse.ai/v1 — 5 call(s), 17915 prompt / 4851 completion tokens

### Files and folders inspected
- /Users/yupe4788/Library/CloudStorage/OneDrive-UCB-O365/Documents/GitHub/LLM_AutoExtracting_CC/ground_truth/pdfs/14_chirinda2010.pdf

### Actions taken
- `workflows/run_extraction.py --project gold_tier1_js2gptoss120b` → 1 row(s) written to `/Users/yupe4788/Library/CloudStorage/OneDrive-UCB-O365/Documents/GitHub/LLM_AutoExtracting_CC/workflows/gold_tier1_js2gptoss120b/output/gold_tier1_js2gptoss120b.csv`
- per-paper report: `/Users/yupe4788/Library/CloudStorage/OneDrive-UCB-O365/Documents/GitHub/LLM_AutoExtracting_CC/workflows/gold_tier1_js2gptoss120b/output/gold_tier1_js2gptoss120b_report.json`

### Verification
- offline sanity_check_row() flags are in the `review_flags` column; response ratios recomputed in code
- external API validation (GBIF/WFO/GeoNames): not run (validate_with_apis not yet wired)

### Flagged for human review
- 14_chirinda2010.pdf: ok — no supported response type detected — Block 2 left blank

### Open questions and follow-up
- review every `low` / `medium` confidence cell against the PDF before merging into the master table

## 2026-09-14

### Prompt
multimodel gold-eval run: model=js2/gpt-oss-120b, paper_id=22

### LLM
js2/gpt-oss-120b via https://llm-api.cyverse.ai/v1 — 6 call(s), 25944 prompt / 7871 completion tokens

### Files and folders inspected
- /Users/yupe4788/Library/CloudStorage/OneDrive-UCB-O365/Documents/GitHub/LLM_AutoExtracting_CC/ground_truth/pdfs/22_dietzel2011.pdf

### Actions taken
- `workflows/run_extraction.py --project gold_tier1_js2gptoss120b` → 4 row(s) written to `/Users/yupe4788/Library/CloudStorage/OneDrive-UCB-O365/Documents/GitHub/LLM_AutoExtracting_CC/workflows/gold_tier1_js2gptoss120b/output/gold_tier1_js2gptoss120b.csv`
- per-paper report: `/Users/yupe4788/Library/CloudStorage/OneDrive-UCB-O365/Documents/GitHub/LLM_AutoExtracting_CC/workflows/gold_tier1_js2gptoss120b/output/gold_tier1_js2gptoss120b_report.json`

### Verification
- offline sanity_check_row() flags are in the `review_flags` column; response ratios recomputed in code
- external API validation (GBIF/WFO/GeoNames): not run (validate_with_apis not yet wired)

### Flagged for human review
- 22_dietzel2011.pdf: ok — no Methods heading found — full-text fallback, Block 1 capped at low

### Open questions and follow-up
- review every `low` / `medium` confidence cell against the PDF before merging into the master table

## 2026-09-14

### Prompt
multimodel gold-eval run: model=js2/gpt-oss-120b, paper_id=27

### LLM
js2/gpt-oss-120b via https://llm-api.cyverse.ai/v1 — 0 call(s), 0 prompt / 0 completion tokens

### Files and folders inspected
- /Users/yupe4788/Library/CloudStorage/OneDrive-UCB-O365/Documents/GitHub/LLM_AutoExtracting_CC/ground_truth/pdfs/27_zhaorigetu2008.pdf

### Actions taken
- `workflows/run_extraction.py --project gold_tier1_js2gptoss120b` → 0 row(s) written to `/Users/yupe4788/Library/CloudStorage/OneDrive-UCB-O365/Documents/GitHub/LLM_AutoExtracting_CC/workflows/gold_tier1_js2gptoss120b/output/gold_tier1_js2gptoss120b.csv`
- per-paper report: `/Users/yupe4788/Library/CloudStorage/OneDrive-UCB-O365/Documents/GitHub/LLM_AutoExtracting_CC/workflows/gold_tier1_js2gptoss120b/output/gold_tier1_js2gptoss120b_report.json`

### Verification
- offline sanity_check_row() flags are in the `review_flags` column; response ratios recomputed in code
- external API validation (GBIF/WFO/GeoNames): not run (validate_with_apis not yet wired)

### Flagged for human review
- 27_zhaorigetu2008.pdf: failed — RuntimeError("LLM call 'enumerate_experimental_units' failed after 4 attempts (max_tokens up to 24000): APITimeoutError('Request timed out.')")

### Open questions and follow-up
- review every `low` / `medium` confidence cell against the PDF before merging into the master table

## 2026-09-14

### Prompt
multimodel gold-eval run: model=js2/gpt-oss-120b, paper_id=34

### LLM
js2/gpt-oss-120b via https://llm-api.cyverse.ai/v1 — 6 call(s), 22022 prompt / 14081 completion tokens

### Files and folders inspected
- /Users/yupe4788/Library/CloudStorage/OneDrive-UCB-O365/Documents/GitHub/LLM_AutoExtracting_CC/ground_truth/pdfs/34_iqbal2015.pdf

### Actions taken
- `workflows/run_extraction.py --project gold_tier1_js2gptoss120b` → 9 row(s) written to `/Users/yupe4788/Library/CloudStorage/OneDrive-UCB-O365/Documents/GitHub/LLM_AutoExtracting_CC/workflows/gold_tier1_js2gptoss120b/output/gold_tier1_js2gptoss120b.csv`
- per-paper report: `/Users/yupe4788/Library/CloudStorage/OneDrive-UCB-O365/Documents/GitHub/LLM_AutoExtracting_CC/workflows/gold_tier1_js2gptoss120b/output/gold_tier1_js2gptoss120b_report.json`

### Verification
- offline sanity_check_row() flags are in the `review_flags` column; response ratios recomputed in code
- external API validation (GBIF/WFO/GeoNames): not run (validate_with_apis not yet wired)

### Flagged for human review
- none

### Open questions and follow-up
- review every `low` / `medium` confidence cell against the PDF before merging into the master table

## 2026-09-14

### Prompt
multimodel gold-eval run: model=js2/gpt-oss-120b, paper_id=35

### LLM
js2/gpt-oss-120b via https://llm-api.cyverse.ai/v1 — 5 call(s), 12505 prompt / 3907 completion tokens

### Files and folders inspected
- /Users/yupe4788/Library/CloudStorage/OneDrive-UCB-O365/Documents/GitHub/LLM_AutoExtracting_CC/ground_truth/pdfs/35_wegner2018.pdf

### Actions taken
- `workflows/run_extraction.py --project gold_tier1_js2gptoss120b` → 1 row(s) written to `/Users/yupe4788/Library/CloudStorage/OneDrive-UCB-O365/Documents/GitHub/LLM_AutoExtracting_CC/workflows/gold_tier1_js2gptoss120b/output/gold_tier1_js2gptoss120b.csv`
- per-paper report: `/Users/yupe4788/Library/CloudStorage/OneDrive-UCB-O365/Documents/GitHub/LLM_AutoExtracting_CC/workflows/gold_tier1_js2gptoss120b/output/gold_tier1_js2gptoss120b_report.json`

### Verification
- offline sanity_check_row() flags are in the `review_flags` column; response ratios recomputed in code
- external API validation (GBIF/WFO/GeoNames): not run (validate_with_apis not yet wired)

### Flagged for human review
- 35_wegner2018.pdf: ok — no supported response type detected — Block 2 left blank

### Open questions and follow-up
- review every `low` / `medium` confidence cell against the PDF before merging into the master table

## 2026-09-14

### Prompt
multimodel gold-eval run: model=js2/gpt-oss-120b, paper_id=39

### LLM
js2/gpt-oss-120b via https://llm-api.cyverse.ai/v1 — 5 call(s), 32786 prompt / 3936 completion tokens

### Files and folders inspected
- /Users/yupe4788/Library/CloudStorage/OneDrive-UCB-O365/Documents/GitHub/LLM_AutoExtracting_CC/ground_truth/pdfs/39_mitchell2013.pdf

### Actions taken
- `workflows/run_extraction.py --project gold_tier1_js2gptoss120b` → 1 row(s) written to `/Users/yupe4788/Library/CloudStorage/OneDrive-UCB-O365/Documents/GitHub/LLM_AutoExtracting_CC/workflows/gold_tier1_js2gptoss120b/output/gold_tier1_js2gptoss120b.csv`
- per-paper report: `/Users/yupe4788/Library/CloudStorage/OneDrive-UCB-O365/Documents/GitHub/LLM_AutoExtracting_CC/workflows/gold_tier1_js2gptoss120b/output/gold_tier1_js2gptoss120b_report.json`

### Verification
- offline sanity_check_row() flags are in the `review_flags` column; response ratios recomputed in code
- external API validation (GBIF/WFO/GeoNames): not run (validate_with_apis not yet wired)

### Flagged for human review
- 39_mitchell2013.pdf: ok — no Methods heading found — full-text fallback, Block 1 capped at low; no supported response type detected — Block 2 left blank

### Open questions and follow-up
- review every `low` / `medium` confidence cell against the PDF before merging into the master table

## 2026-09-14

### Prompt
multimodel gold-eval run: model=js2/gpt-oss-120b, paper_id=41

### LLM
js2/gpt-oss-120b via https://llm-api.cyverse.ai/v1 — 6 call(s), 44042 prompt / 9968 completion tokens

### Files and folders inspected
- /Users/yupe4788/Library/CloudStorage/OneDrive-UCB-O365/Documents/GitHub/LLM_AutoExtracting_CC/ground_truth/pdfs/41_thomas2017.pdf

### Actions taken
- `workflows/run_extraction.py --project gold_tier1_js2gptoss120b` → 4 row(s) written to `/Users/yupe4788/Library/CloudStorage/OneDrive-UCB-O365/Documents/GitHub/LLM_AutoExtracting_CC/workflows/gold_tier1_js2gptoss120b/output/gold_tier1_js2gptoss120b.csv`
- per-paper report: `/Users/yupe4788/Library/CloudStorage/OneDrive-UCB-O365/Documents/GitHub/LLM_AutoExtracting_CC/workflows/gold_tier1_js2gptoss120b/output/gold_tier1_js2gptoss120b_report.json`

### Verification
- offline sanity_check_row() flags are in the `review_flags` column; response ratios recomputed in code
- external API validation (GBIF/WFO/GeoNames): not run (validate_with_apis not yet wired)

### Flagged for human review
- none

### Open questions and follow-up
- review every `low` / `medium` confidence cell against the PDF before merging into the master table

## 2026-09-14

### Prompt
multimodel gold-eval run: model=js2/gpt-oss-120b, paper_id=2

### LLM
js2/gpt-oss-120b via https://llm-api.cyverse.ai/v1 — 8 call(s), 53045 prompt / 41160 completion tokens

### Files and folders inspected
- /Users/yupe4788/Library/CloudStorage/OneDrive-UCB-O365/Documents/GitHub/LLM_AutoExtracting_CC/ground_truth/pdfs/2_li2015.pdf

### Actions taken
- `workflows/run_extraction.py --project gold_tier1_js2gptoss120b` → 19 row(s) written to `/Users/yupe4788/Library/CloudStorage/OneDrive-UCB-O365/Documents/GitHub/LLM_AutoExtracting_CC/workflows/gold_tier1_js2gptoss120b/output/gold_tier1_js2gptoss120b.csv`
- per-paper report: `/Users/yupe4788/Library/CloudStorage/OneDrive-UCB-O365/Documents/GitHub/LLM_AutoExtracting_CC/workflows/gold_tier1_js2gptoss120b/output/gold_tier1_js2gptoss120b_report.json`

### Verification
- offline sanity_check_row() flags are in the `review_flags` column; response ratios recomputed in code
- external API validation (GBIF/WFO/GeoNames): not run (validate_with_apis not yet wired)

### Flagged for human review
- none

### Open questions and follow-up
- review every `low` / `medium` confidence cell against the PDF before merging into the master table

## 2026-09-14

### Prompt
multimodel gold-eval run: model=js2/gpt-oss-120b, paper_id=6

### LLM
js2/gpt-oss-120b via https://llm-api.cyverse.ai/v1 — 6 call(s), 33814 prompt / 8231 completion tokens

### Files and folders inspected
- /Users/yupe4788/Library/CloudStorage/OneDrive-UCB-O365/Documents/GitHub/LLM_AutoExtracting_CC/ground_truth/pdfs/6_sapkota2017.pdf

### Actions taken
- `workflows/run_extraction.py --project gold_tier1_js2gptoss120b` → 3 row(s) written to `/Users/yupe4788/Library/CloudStorage/OneDrive-UCB-O365/Documents/GitHub/LLM_AutoExtracting_CC/workflows/gold_tier1_js2gptoss120b/output/gold_tier1_js2gptoss120b.csv`
- per-paper report: `/Users/yupe4788/Library/CloudStorage/OneDrive-UCB-O365/Documents/GitHub/LLM_AutoExtracting_CC/workflows/gold_tier1_js2gptoss120b/output/gold_tier1_js2gptoss120b_report.json`

### Verification
- offline sanity_check_row() flags are in the `review_flags` column; response ratios recomputed in code
- external API validation (GBIF/WFO/GeoNames): not run (validate_with_apis not yet wired)

### Flagged for human review
- none

### Open questions and follow-up
- review every `low` / `medium` confidence cell against the PDF before merging into the master table

## 2026-09-14

### Prompt
multimodel gold-eval run: model=js2/gpt-oss-120b, paper_id=10

### LLM
js2/gpt-oss-120b via https://llm-api.cyverse.ai/v1 — 10 call(s), 31663 prompt / 19932 completion tokens

### Files and folders inspected
- /Users/yupe4788/Library/CloudStorage/OneDrive-UCB-O365/Documents/GitHub/LLM_AutoExtracting_CC/ground_truth/pdfs/10_haque2015.pdf

### Actions taken
- `workflows/run_extraction.py --project gold_tier1_js2gptoss120b` → 12 row(s) written to `/Users/yupe4788/Library/CloudStorage/OneDrive-UCB-O365/Documents/GitHub/LLM_AutoExtracting_CC/workflows/gold_tier1_js2gptoss120b/output/gold_tier1_js2gptoss120b.csv`
- per-paper report: `/Users/yupe4788/Library/CloudStorage/OneDrive-UCB-O365/Documents/GitHub/LLM_AutoExtracting_CC/workflows/gold_tier1_js2gptoss120b/output/gold_tier1_js2gptoss120b_report.json`

### Verification
- offline sanity_check_row() flags are in the `review_flags` column; response ratios recomputed in code
- external API validation (GBIF/WFO/GeoNames): not run (validate_with_apis not yet wired)

### Flagged for human review
- none

### Open questions and follow-up
- review every `low` / `medium` confidence cell against the PDF before merging into the master table

## 2026-09-14

### Prompt
multimodel gold-eval run: model=js2/gpt-oss-120b, paper_id=11

### LLM
js2/gpt-oss-120b via https://llm-api.cyverse.ai/v1 — 6 call(s), 26434 prompt / 15107 completion tokens

### Files and folders inspected
- /Users/yupe4788/Library/CloudStorage/OneDrive-UCB-O365/Documents/GitHub/LLM_AutoExtracting_CC/ground_truth/pdfs/11_weiler2018.pdf

### Actions taken
- `workflows/run_extraction.py --project gold_tier1_js2gptoss120b` → 12 row(s) written to `/Users/yupe4788/Library/CloudStorage/OneDrive-UCB-O365/Documents/GitHub/LLM_AutoExtracting_CC/workflows/gold_tier1_js2gptoss120b/output/gold_tier1_js2gptoss120b.csv`
- per-paper report: `/Users/yupe4788/Library/CloudStorage/OneDrive-UCB-O365/Documents/GitHub/LLM_AutoExtracting_CC/workflows/gold_tier1_js2gptoss120b/output/gold_tier1_js2gptoss120b_report.json`

### Verification
- offline sanity_check_row() flags are in the `review_flags` column; response ratios recomputed in code
- external API validation (GBIF/WFO/GeoNames): not run (validate_with_apis not yet wired)

### Flagged for human review
- none

### Open questions and follow-up
- review every `low` / `medium` confidence cell against the PDF before merging into the master table

## 2026-09-14

### Prompt
multimodel gold-eval run: model=js2/gpt-oss-120b, paper_id=14

### LLM
js2/gpt-oss-120b via https://llm-api.cyverse.ai/v1 — 5 call(s), 17915 prompt / 4462 completion tokens

### Files and folders inspected
- /Users/yupe4788/Library/CloudStorage/OneDrive-UCB-O365/Documents/GitHub/LLM_AutoExtracting_CC/ground_truth/pdfs/14_chirinda2010.pdf

### Actions taken
- `workflows/run_extraction.py --project gold_tier1_js2gptoss120b` → 1 row(s) written to `/Users/yupe4788/Library/CloudStorage/OneDrive-UCB-O365/Documents/GitHub/LLM_AutoExtracting_CC/workflows/gold_tier1_js2gptoss120b/output/gold_tier1_js2gptoss120b.csv`
- per-paper report: `/Users/yupe4788/Library/CloudStorage/OneDrive-UCB-O365/Documents/GitHub/LLM_AutoExtracting_CC/workflows/gold_tier1_js2gptoss120b/output/gold_tier1_js2gptoss120b_report.json`

### Verification
- offline sanity_check_row() flags are in the `review_flags` column; response ratios recomputed in code
- external API validation (GBIF/WFO/GeoNames): not run (validate_with_apis not yet wired)

### Flagged for human review
- 14_chirinda2010.pdf: ok — no supported response type detected — Block 2 left blank

### Open questions and follow-up
- review every `low` / `medium` confidence cell against the PDF before merging into the master table

## 2026-09-14

### Prompt
multimodel gold-eval run: model=js2/gpt-oss-120b, paper_id=22

### LLM
js2/gpt-oss-120b via https://llm-api.cyverse.ai/v1 — 6 call(s), 25944 prompt / 8059 completion tokens

### Files and folders inspected
- /Users/yupe4788/Library/CloudStorage/OneDrive-UCB-O365/Documents/GitHub/LLM_AutoExtracting_CC/ground_truth/pdfs/22_dietzel2011.pdf

### Actions taken
- `workflows/run_extraction.py --project gold_tier1_js2gptoss120b` → 4 row(s) written to `/Users/yupe4788/Library/CloudStorage/OneDrive-UCB-O365/Documents/GitHub/LLM_AutoExtracting_CC/workflows/gold_tier1_js2gptoss120b/output/gold_tier1_js2gptoss120b.csv`
- per-paper report: `/Users/yupe4788/Library/CloudStorage/OneDrive-UCB-O365/Documents/GitHub/LLM_AutoExtracting_CC/workflows/gold_tier1_js2gptoss120b/output/gold_tier1_js2gptoss120b_report.json`

### Verification
- offline sanity_check_row() flags are in the `review_flags` column; response ratios recomputed in code
- external API validation (GBIF/WFO/GeoNames): not run (validate_with_apis not yet wired)

### Flagged for human review
- 22_dietzel2011.pdf: ok — no Methods heading found — full-text fallback, Block 1 capped at low

### Open questions and follow-up
- review every `low` / `medium` confidence cell against the PDF before merging into the master table

## 2026-09-14

### Prompt
multimodel gold-eval run: model=js2/gpt-oss-120b, paper_id=27

### LLM
js2/gpt-oss-120b via https://llm-api.cyverse.ai/v1 — 7 call(s), 30665 prompt / 42387 completion tokens

### Files and folders inspected
- /Users/yupe4788/Library/CloudStorage/OneDrive-UCB-O365/Documents/GitHub/LLM_AutoExtracting_CC/ground_truth/pdfs/27_zhaorigetu2008.pdf

### Actions taken
- `workflows/run_extraction.py --project gold_tier1_js2gptoss120b` → 17 row(s) written to `/Users/yupe4788/Library/CloudStorage/OneDrive-UCB-O365/Documents/GitHub/LLM_AutoExtracting_CC/workflows/gold_tier1_js2gptoss120b/output/gold_tier1_js2gptoss120b.csv`
- per-paper report: `/Users/yupe4788/Library/CloudStorage/OneDrive-UCB-O365/Documents/GitHub/LLM_AutoExtracting_CC/workflows/gold_tier1_js2gptoss120b/output/gold_tier1_js2gptoss120b_report.json`

### Verification
- offline sanity_check_row() flags are in the `review_flags` column; response ratios recomputed in code
- external API validation (GBIF/WFO/GeoNames): not run (validate_with_apis not yet wired)

### Flagged for human review
- none

### Open questions and follow-up
- review every `low` / `medium` confidence cell against the PDF before merging into the master table

## 2026-09-14

### Prompt
multimodel gold-eval run: model=js2/gpt-oss-120b, paper_id=34

### LLM
js2/gpt-oss-120b via https://llm-api.cyverse.ai/v1 — 6 call(s), 22022 prompt / 18475 completion tokens

### Files and folders inspected
- /Users/yupe4788/Library/CloudStorage/OneDrive-UCB-O365/Documents/GitHub/LLM_AutoExtracting_CC/ground_truth/pdfs/34_iqbal2015.pdf

### Actions taken
- `workflows/run_extraction.py --project gold_tier1_js2gptoss120b` → 12 row(s) written to `/Users/yupe4788/Library/CloudStorage/OneDrive-UCB-O365/Documents/GitHub/LLM_AutoExtracting_CC/workflows/gold_tier1_js2gptoss120b/output/gold_tier1_js2gptoss120b.csv`
- per-paper report: `/Users/yupe4788/Library/CloudStorage/OneDrive-UCB-O365/Documents/GitHub/LLM_AutoExtracting_CC/workflows/gold_tier1_js2gptoss120b/output/gold_tier1_js2gptoss120b_report.json`

### Verification
- offline sanity_check_row() flags are in the `review_flags` column; response ratios recomputed in code
- external API validation (GBIF/WFO/GeoNames): not run (validate_with_apis not yet wired)

### Flagged for human review
- none

### Open questions and follow-up
- review every `low` / `medium` confidence cell against the PDF before merging into the master table

## 2026-09-14

### Prompt
multimodel gold-eval run: model=js2/gpt-oss-120b, paper_id=35

### LLM
js2/gpt-oss-120b via https://llm-api.cyverse.ai/v1 — 5 call(s), 12505 prompt / 3900 completion tokens

### Files and folders inspected
- /Users/yupe4788/Library/CloudStorage/OneDrive-UCB-O365/Documents/GitHub/LLM_AutoExtracting_CC/ground_truth/pdfs/35_wegner2018.pdf

### Actions taken
- `workflows/run_extraction.py --project gold_tier1_js2gptoss120b` → 1 row(s) written to `/Users/yupe4788/Library/CloudStorage/OneDrive-UCB-O365/Documents/GitHub/LLM_AutoExtracting_CC/workflows/gold_tier1_js2gptoss120b/output/gold_tier1_js2gptoss120b.csv`
- per-paper report: `/Users/yupe4788/Library/CloudStorage/OneDrive-UCB-O365/Documents/GitHub/LLM_AutoExtracting_CC/workflows/gold_tier1_js2gptoss120b/output/gold_tier1_js2gptoss120b_report.json`

### Verification
- offline sanity_check_row() flags are in the `review_flags` column; response ratios recomputed in code
- external API validation (GBIF/WFO/GeoNames): not run (validate_with_apis not yet wired)

### Flagged for human review
- 35_wegner2018.pdf: ok — no supported response type detected — Block 2 left blank

### Open questions and follow-up
- review every `low` / `medium` confidence cell against the PDF before merging into the master table

## 2026-09-14

### Prompt
multimodel gold-eval run: model=js2/gpt-oss-120b, paper_id=39

### LLM
js2/gpt-oss-120b via https://llm-api.cyverse.ai/v1 — 5 call(s), 32786 prompt / 3612 completion tokens

### Files and folders inspected
- /Users/yupe4788/Library/CloudStorage/OneDrive-UCB-O365/Documents/GitHub/LLM_AutoExtracting_CC/ground_truth/pdfs/39_mitchell2013.pdf

### Actions taken
- `workflows/run_extraction.py --project gold_tier1_js2gptoss120b` → 1 row(s) written to `/Users/yupe4788/Library/CloudStorage/OneDrive-UCB-O365/Documents/GitHub/LLM_AutoExtracting_CC/workflows/gold_tier1_js2gptoss120b/output/gold_tier1_js2gptoss120b.csv`
- per-paper report: `/Users/yupe4788/Library/CloudStorage/OneDrive-UCB-O365/Documents/GitHub/LLM_AutoExtracting_CC/workflows/gold_tier1_js2gptoss120b/output/gold_tier1_js2gptoss120b_report.json`

### Verification
- offline sanity_check_row() flags are in the `review_flags` column; response ratios recomputed in code
- external API validation (GBIF/WFO/GeoNames): not run (validate_with_apis not yet wired)

### Flagged for human review
- 39_mitchell2013.pdf: ok — no Methods heading found — full-text fallback, Block 1 capped at low; no supported response type detected — Block 2 left blank

### Open questions and follow-up
- review every `low` / `medium` confidence cell against the PDF before merging into the master table

## 2026-09-14

### Prompt
multimodel gold-eval run: model=js2/gpt-oss-120b, paper_id=41

### LLM
js2/gpt-oss-120b via https://llm-api.cyverse.ai/v1 — 6 call(s), 44042 prompt / 12524 completion tokens

### Files and folders inspected
- /Users/yupe4788/Library/CloudStorage/OneDrive-UCB-O365/Documents/GitHub/LLM_AutoExtracting_CC/ground_truth/pdfs/41_thomas2017.pdf

### Actions taken
- `workflows/run_extraction.py --project gold_tier1_js2gptoss120b` → 8 row(s) written to `/Users/yupe4788/Library/CloudStorage/OneDrive-UCB-O365/Documents/GitHub/LLM_AutoExtracting_CC/workflows/gold_tier1_js2gptoss120b/output/gold_tier1_js2gptoss120b.csv`
- per-paper report: `/Users/yupe4788/Library/CloudStorage/OneDrive-UCB-O365/Documents/GitHub/LLM_AutoExtracting_CC/workflows/gold_tier1_js2gptoss120b/output/gold_tier1_js2gptoss120b_report.json`

### Verification
- offline sanity_check_row() flags are in the `review_flags` column; response ratios recomputed in code
- external API validation (GBIF/WFO/GeoNames): not run (validate_with_apis not yet wired)

### Flagged for human review
- none

### Open questions and follow-up
- review every `low` / `medium` confidence cell against the PDF before merging into the master table

## 2026-09-14

### Prompt
multimodel gold-eval run: model=nrp/glm-5, paper_id=2

### LLM
nrp/glm-5 via https://llm-api.cyverse.ai/v1 — 0 call(s), 0 prompt / 0 completion tokens

### Files and folders inspected
- /Users/yupe4788/Library/CloudStorage/OneDrive-UCB-O365/Documents/GitHub/LLM_AutoExtracting_CC/ground_truth/pdfs/2_li2015.pdf

### Actions taken
- `workflows/run_extraction.py --project gold_tier1_nrpglm5` → 0 row(s) written to `/Users/yupe4788/Library/CloudStorage/OneDrive-UCB-O365/Documents/GitHub/LLM_AutoExtracting_CC/workflows/gold_tier1_nrpglm5/output/gold_tier1_nrpglm5.csv`
- per-paper report: `/Users/yupe4788/Library/CloudStorage/OneDrive-UCB-O365/Documents/GitHub/LLM_AutoExtracting_CC/workflows/gold_tier1_nrpglm5/output/gold_tier1_nrpglm5_report.json`

### Verification
- offline sanity_check_row() flags are in the `review_flags` column; response ratios recomputed in code
- external API validation (GBIF/WFO/GeoNames): not run (validate_with_apis not yet wired)

### Flagged for human review
- 2_li2015.pdf: failed — RuntimeError("LLM call 'classify_response_type' failed after 4 attempts (max_tokens up to 8000): APITimeoutError('Request timed out.')")

### Open questions and follow-up
- review every `low` / `medium` confidence cell against the PDF before merging into the master table

## 2026-09-14

### Prompt
multimodel gold-eval run: model=nrp/glm-5, paper_id=6

### LLM
nrp/glm-5 via https://llm-api.cyverse.ai/v1 — 0 call(s), 0 prompt / 0 completion tokens

### Files and folders inspected
- /Users/yupe4788/Library/CloudStorage/OneDrive-UCB-O365/Documents/GitHub/LLM_AutoExtracting_CC/ground_truth/pdfs/6_sapkota2017.pdf

### Actions taken
- `workflows/run_extraction.py --project gold_tier1_nrpglm5` → 0 row(s) written to `/Users/yupe4788/Library/CloudStorage/OneDrive-UCB-O365/Documents/GitHub/LLM_AutoExtracting_CC/workflows/gold_tier1_nrpglm5/output/gold_tier1_nrpglm5.csv`
- per-paper report: `/Users/yupe4788/Library/CloudStorage/OneDrive-UCB-O365/Documents/GitHub/LLM_AutoExtracting_CC/workflows/gold_tier1_nrpglm5/output/gold_tier1_nrpglm5_report.json`

### Verification
- offline sanity_check_row() flags are in the `review_flags` column; response ratios recomputed in code
- external API validation (GBIF/WFO/GeoNames): not run (validate_with_apis not yet wired)

### Flagged for human review
- 6_sapkota2017.pdf: failed — RuntimeError("LLM call 'enumerate_experimental_units' failed after 4 attempts (max_tokens up to 16000): APITimeoutError('Request timed out.')")

### Open questions and follow-up
- review every `low` / `medium` confidence cell against the PDF before merging into the master table

## 2026-09-14

### Prompt
multimodel gold-eval run: model=nrp/glm-5, paper_id=10

### LLM
nrp/glm-5 via https://llm-api.cyverse.ai/v1 — 0 call(s), 0 prompt / 0 completion tokens

### Files and folders inspected
- /Users/yupe4788/Library/CloudStorage/OneDrive-UCB-O365/Documents/GitHub/LLM_AutoExtracting_CC/ground_truth/pdfs/10_haque2015.pdf

### Actions taken
- `workflows/run_extraction.py --project gold_tier1_nrpglm5` → 0 row(s) written to `/Users/yupe4788/Library/CloudStorage/OneDrive-UCB-O365/Documents/GitHub/LLM_AutoExtracting_CC/workflows/gold_tier1_nrpglm5/output/gold_tier1_nrpglm5.csv`
- per-paper report: `/Users/yupe4788/Library/CloudStorage/OneDrive-UCB-O365/Documents/GitHub/LLM_AutoExtracting_CC/workflows/gold_tier1_nrpglm5/output/gold_tier1_nrpglm5_report.json`

### Verification
- offline sanity_check_row() flags are in the `review_flags` column; response ratios recomputed in code
- external API validation (GBIF/WFO/GeoNames): not run (validate_with_apis not yet wired)

### Flagged for human review
- 10_haque2015.pdf: failed — RuntimeError("LLM call 'enumerate_experimental_units' failed after 4 attempts (max_tokens up to 16000): APITimeoutError('Request timed out.')")

### Open questions and follow-up
- review every `low` / `medium` confidence cell against the PDF before merging into the master table

## 2026-09-14

### Prompt
multimodel gold-eval run: model=nrp/glm-5, paper_id=11

### LLM
nrp/glm-5 via https://llm-api.cyverse.ai/v1 — 0 call(s), 0 prompt / 0 completion tokens

### Files and folders inspected
- /Users/yupe4788/Library/CloudStorage/OneDrive-UCB-O365/Documents/GitHub/LLM_AutoExtracting_CC/ground_truth/pdfs/11_weiler2018.pdf

### Actions taken
- `workflows/run_extraction.py --project gold_tier1_nrpglm5` → 0 row(s) written to `/Users/yupe4788/Library/CloudStorage/OneDrive-UCB-O365/Documents/GitHub/LLM_AutoExtracting_CC/workflows/gold_tier1_nrpglm5/output/gold_tier1_nrpglm5.csv`
- per-paper report: `/Users/yupe4788/Library/CloudStorage/OneDrive-UCB-O365/Documents/GitHub/LLM_AutoExtracting_CC/workflows/gold_tier1_nrpglm5/output/gold_tier1_nrpglm5_report.json`

### Verification
- offline sanity_check_row() flags are in the `review_flags` column; response ratios recomputed in code
- external API validation (GBIF/WFO/GeoNames): not run (validate_with_apis not yet wired)

### Flagged for human review
- 11_weiler2018.pdf: failed — RuntimeError("LLM call 'enumerate_experimental_units' failed after 4 attempts (max_tokens up to 16000): APITimeoutError('Request timed out.')")

### Open questions and follow-up
- review every `low` / `medium` confidence cell against the PDF before merging into the master table

## 2026-09-14

### Prompt
multimodel gold-eval run: model=nrp/glm-5, paper_id=14

### LLM
nrp/glm-5 via https://llm-api.cyverse.ai/v1 — 0 call(s), 0 prompt / 0 completion tokens

### Files and folders inspected
- /Users/yupe4788/Library/CloudStorage/OneDrive-UCB-O365/Documents/GitHub/LLM_AutoExtracting_CC/ground_truth/pdfs/14_chirinda2010.pdf

### Actions taken
- `workflows/run_extraction.py --project gold_tier1_nrpglm5` → 0 row(s) written to `/Users/yupe4788/Library/CloudStorage/OneDrive-UCB-O365/Documents/GitHub/LLM_AutoExtracting_CC/workflows/gold_tier1_nrpglm5/output/gold_tier1_nrpglm5.csv`
- per-paper report: `/Users/yupe4788/Library/CloudStorage/OneDrive-UCB-O365/Documents/GitHub/LLM_AutoExtracting_CC/workflows/gold_tier1_nrpglm5/output/gold_tier1_nrpglm5_report.json`

### Verification
- offline sanity_check_row() flags are in the `review_flags` column; response ratios recomputed in code
- external API validation (GBIF/WFO/GeoNames): not run (validate_with_apis not yet wired)

### Flagged for human review
- 14_chirinda2010.pdf: failed — RuntimeError("LLM call 'classify_response_type' failed after 4 attempts (max_tokens up to 8000): APITimeoutError('Request timed out.')")

### Open questions and follow-up
- review every `low` / `medium` confidence cell against the PDF before merging into the master table
