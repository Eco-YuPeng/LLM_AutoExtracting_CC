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
