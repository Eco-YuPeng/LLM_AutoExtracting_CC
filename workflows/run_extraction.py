#!/usr/bin/env python3
"""
run_extraction.py — generic command-line runner for the extraction pipeline.

    python workflows/run_extraction.py --project franco2021_test \
        --pdf workflows/franco2021_test/input/*.pdf

    python workflows/run_extraction.py --project batch1 --pdf-dir test_pdfs/ \
        --model anthropic/claude-sonnet-4

Options
  --project NAME        output goes to workflows/NAME/output/NAME.csv (+ _report.json)
  --pdf PATH [PATH...]  one or more PDFs
  --pdf-dir DIR         every *.pdf in DIR
  --paper-id N          paper_id for a single PDF (optional)
  --no-llm              deterministic stages only (no API key needed)
  --exclude-proposed    skip schema fields with status proposed_new (soc/nitrogen
                        blocks, doi, response_types_detected). Default: populate them —
                        they are flagged proposed_new in the schema for review, but the
                        pipeline needs them to be useful.
  --model NAME          override LLM_MODEL for this run
  --api-base URL        override LLM_API_BASE for this run
  --prompt TEXT         the user's exact request, copied into PROMPT_ACTION_LOG.md

Environment: OPENAI_API_KEY (required unless --no-llm), LLM_API_BASE, LLM_MODEL.
"""

import argparse
import datetime as dt
import json
import os
import sys
from pathlib import Path

_repo_root = next(p for p in Path(__file__).resolve().parents
                  if (p / "src" / "literature_extractor.py").exists())
sys.path.insert(0, str(_repo_root))

from src import llm_client  # noqa: E402
from src.literature_extractor import (  # noqa: E402
    ExtractionWorkflow,
    PaperSpec,
    run_extraction,
)


def _append_log(project: str, prompt: str, model: str, pdfs: list[Path], out_dir: Path, reports_path: Path) -> None:
    reports = json.loads(reports_path.read_text(encoding="utf-8")) if reports_path.exists() else []
    n_rows = sum(r.get("n_rows", 0) for r in reports)
    calls = [c for r in reports for c in r.get("llm_calls", [])]
    tok_in = sum(c.get("prompt_tokens") or 0 for c in calls)
    tok_out = sum(c.get("completion_tokens") or 0 for c in calls)
    flagged = [f"{Path(r['pdf']).name}: {r['status']} — {'; '.join(r.get('notes', []))}"
               for r in reports if r.get("status") != "ok" or r.get("notes")]
    entry = f"""
## {dt.date.today().isoformat()}

### Prompt
{prompt or '(run via workflows/run_extraction.py, no prompt text given)'}

### LLM
{model} via {os.environ.get('LLM_API_BASE', llm_client.DEFAULT_API_BASE)} — {len(calls)} call(s), {tok_in} prompt / {tok_out} completion tokens

### Files and folders inspected
{chr(10).join(f'- {p}' for p in pdfs)}

### Actions taken
- `workflows/run_extraction.py --project {project}` → {n_rows} row(s) written to `{out_dir / (project + '.csv')}`
- per-paper report: `{reports_path}`

### Verification
- offline sanity_check_row() flags are in the `review_flags` column; response ratios recomputed in code
- external API validation (GBIF/WFO/GeoNames): not run (validate_with_apis not yet wired)

### Flagged for human review
{chr(10).join(f'- {f}' for f in flagged) or '- none'}

### Open questions and follow-up
- review every `low` / `medium` confidence cell against the PDF before merging into the master table
"""
    with open(_repo_root / "PROMPT_ACTION_LOG.md", "a", encoding="utf-8") as f:
        f.write(entry)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", required=True)
    ap.add_argument("--pdf", nargs="*", default=[])
    ap.add_argument("--pdf-dir")
    ap.add_argument("--paper-id", type=int)
    ap.add_argument("--no-llm", action="store_true")
    ap.add_argument("--exclude-proposed", action="store_true")
    ap.add_argument("--model")
    ap.add_argument("--api-base")
    ap.add_argument("--prompt", default="")
    args = ap.parse_args()

    if args.model:
        os.environ["LLM_MODEL"] = args.model
    if args.api_base:
        os.environ["LLM_API_BASE"] = args.api_base

    pdfs = [Path(p) for p in args.pdf]
    if args.pdf_dir:
        pdfs += sorted(Path(args.pdf_dir).glob("*.pdf"))
    if not pdfs:
        ap.error("no PDFs given (--pdf or --pdf-dir)")

    if not args.no_llm and not os.environ.get("OPENAI_API_KEY"):
        print("OPENAI_API_KEY not set — export your AI Verde key, or pass --no-llm.", file=sys.stderr)
        return 2

    cfg = llm_client.LLMConfig.from_env()
    out_dir = _repo_root / "workflows" / args.project / "output"
    papers = [PaperSpec(pdf_path=p, paper_id=args.paper_id if len(pdfs) == 1 else None) for p in pdfs]
    wf = ExtractionWorkflow(name=args.project, papers=papers, output_dir=out_dir)

    rows = run_extraction(wf, use_llm=not args.no_llm, include_proposed=not args.exclude_proposed, cfg=cfg)
    _append_log(args.project, args.prompt, "none (--no-llm)" if args.no_llm else cfg.model,
                pdfs, out_dir, out_dir / f"{args.project}_report.json")
    print(f"done: {len(rows)} row(s) from {len(pdfs)} PDF(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
