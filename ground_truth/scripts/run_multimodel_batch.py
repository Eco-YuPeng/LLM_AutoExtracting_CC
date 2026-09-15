#!/usr/bin/env python3
"""
Run the extraction pipeline over every PDF in ground_truth/pdfs/ through
each of several models, one run_extraction.py call per (paper, model), so
ground_truth/scripts/merge_multimodel_consensus.py can vote across the
results afterward.

MUST be run somewhere with direct internet access to the LLM gateway
(llm-api.cyverse.ai / AI Verde) -- e.g. your own machine's regular
terminal, or CyVerse. The Claude session's device_bash shell CANNOT reach
that gateway (its network goes through an org policy proxy that blocks
llm-api.cyverse.ai) -- this script will just fail with connection errors
if run from there.

Usage:
    export OPENAI_API_KEY=<your AI Verde key>
    python3 ground_truth/scripts/run_multimodel_batch.py

    # preview the exact commands without calling any model or API:
    python3 ground_truth/scripts/run_multimodel_batch.py --dry-run

Resume behavior (default ON): a (paper_id, model) pair is SKIPPED if that
paper_id already has at least one row in workflows/<project>/output/
<project>.csv from a prior run -- so a run interrupted partway through
(Ctrl+C, a hung/timing-out paper, a crash) can just be re-launched with
the exact same command and it only (re)does the papers that are still
missing, instead of re-spending real LLM calls re-extracting papers that
already succeeded. Pass --force to disable this and redo every paper
regardless -- use that after a code/prompt change that should invalidate
previously-extracted rows.

Optional:
    --pdf-dir DIR        default: ground_truth/pdfs
    --models a,b,c       default: js2/gpt-oss-120b,nrp/glm-5,nrp/kimi
    --project-prefix P   default: gold_tier1  ->  workflows/<P>_<model_slug>/
    --force              ignore prior results, (re)run every paper

Filename convention expected in --pdf-dir: "<paper_id>_<anything>.pdf"
(e.g. "2_li2015.pdf") -- the leading number before the first underscore is
used as --paper-id, so pipeline output rows line up with
ground_truth/output/gold_eval_ghg_tier1.csv (paper_id column) for scoring.

After this finishes, merge the per-model CSVs and score against gold:

    python3 ground_truth/scripts/merge_multimodel_consensus.py \\
        --input "gpt-oss-120b=workflows/gold_tier1_<slug1>/output/gold_tier1_<slug1>.csv" \\
        --input "glm-5=workflows/gold_tier1_<slug2>/output/gold_tier1_<slug2>.csv" \\
        --input "kimi=workflows/gold_tier1_<slug3>/output/gold_tier1_<slug3>.csv" \\
        --out-dir ground_truth/output/consensus_run_<date>/

    python3 ground_truth/scripts/score_pipeline_output.py \\
        --pipeline-csv ground_truth/output/consensus_run_<date>/consensus.csv \\
        --gold-csv ground_truth/output/gold_eval_ghg_tier1.csv \\
        --out-dir ground_truth/output/scoring_run_<date>/

(this script prints the exact slugs it used for each model at the end, to
copy into those commands)
"""
import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

_repo_root = next(p for p in Path(__file__).resolve().parents
                   if (p / "workflows" / "run_extraction.py").exists())

DEFAULT_MODELS = ["js2/gpt-oss-120b", "nrp/glm-5", "nrp/kimi"]

# Per-model env overrides applied ONLY to that model's subprocess calls.
# nrp/glm-5 was observed (2026-09 gold-eval run) timing out on the large
# majority of calls at the hard 180s request timeout -- not a token-budget
# problem (many failing calls were small extract_narrow_llm batches, not
# the big enumerate_experimental_units call) but a reasoning-time problem:
# its reasoning_content routinely ran 8000-16000+ chars even for small
# asks, several times any other model's. src/llm_client.py already has a
# documented, opt-in fix for exactly this (LLM_DISABLE_THINKING=1, a
# Qwen/GLM-style flag that skips chain-of-thought -- "a ~50x speedup on
# that model" per its own comment) that was never actually being set for
# these runs. Applied per-model, not globally, because other
# models/deployments on the same gateway may reject the extra_body key.
#
# nrp/kimi was ALSO tried with this flag (2026-09) and it did NOT help --
# reasoning_chars stayed in the same 5000-12000 range with or without it,
# so kimi's slowness isn't gated by this switch. Left unset for kimi
# rather than applied uselessly.
PER_MODEL_ENV = {
    "nrp/glm-5": {"LLM_DISABLE_THINKING": "1"},
}


def slugify(model: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", model.lower())


def _already_done_paper_ids(project: str) -> set[int]:
    """
    paper_ids that already have at least one row in this project's output
    CSV from a prior run -- the resume signal. Missing/unreadable/empty
    CSV just means "nothing done yet", not an error.
    """
    csv_path = _repo_root / "workflows" / project / "output" / f"{project}.csv"
    if not csv_path.exists():
        return set()
    try:
        import pandas as pd
        df = pd.read_csv(csv_path)
        if "paper_id" not in df.columns:
            return set()
        return set(int(x) for x in df["paper_id"].dropna().unique())
    except Exception as e:  # noqa: BLE001 -- a bad/partial CSV just means "resume from scratch"
        print(f"  (couldn't read {csv_path} to check resume state: {e!r} -- treating as none done)", file=sys.stderr)
        return set()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pdf-dir", default=str(_repo_root / "ground_truth" / "pdfs"))
    ap.add_argument("--models", default=",".join(DEFAULT_MODELS))
    ap.add_argument("--project-prefix", default="gold_tier1")
    ap.add_argument("--dry-run", action="store_true", help="print commands, call nothing")
    ap.add_argument("--force", action="store_true",
                     help="ignore prior results and (re)run every paper, even ones already "
                          "present in the project's output CSV")
    args = ap.parse_args()

    if not args.dry_run and not os.environ.get("OPENAI_API_KEY"):
        print("OPENAI_API_KEY is not set -- export your AI Verde key first "
              "(or pass --dry-run to just preview commands).", file=sys.stderr)
        return 2

    pdf_dir = Path(args.pdf_dir)
    pdfs = sorted(pdf_dir.glob("*.pdf"))
    if not pdfs:
        print(f"No PDFs found in {pdf_dir}", file=sys.stderr)
        return 2

    papers, skipped = [], []
    for pdf in pdfs:
        m = re.match(r"^(\d+)_", pdf.name)
        if not m:
            skipped.append(pdf.name)
            continue
        papers.append((int(m.group(1)), pdf))
    for name in skipped:
        print(f"SKIP {name}: filename doesn't start with '<paper_id>_' -- rename it first.", file=sys.stderr)

    models = [m.strip() for m in args.models.split(",") if m.strip()]
    slugs = {m: slugify(m) for m in models}
    print(f"{len(papers)} paper(s) x {len(models)} model(s) = {len(papers) * len(models)} run(s) (before resume skip)")
    print("model -> project slug:")
    for m, s in slugs.items():
        print(f"  {m:20s} -> {args.project_prefix}_{s}")
    print()

    failures = []
    for model in models:
        project = f"{args.project_prefix}_{slugs[model]}"
        done_ids = set() if args.force else _already_done_paper_ids(project)
        if done_ids:
            print(f"  resume: {len(done_ids)} paper(s) already in workflows/{project}/output/{project}.csv "
                  f"-- will skip {sorted(done_ids)}")
        print(f"\n=== model={model}  ->  workflows/{project}/output/{project}.csv ===")
        for paper_id, pdf in sorted(papers):
            if paper_id in done_ids:
                print(f"--- paper_id={paper_id}  {pdf.name}: SKIP (already done, use --force to redo) ---")
                continue
            cmd = [
                sys.executable, str(_repo_root / "workflows" / "run_extraction.py"),
                "--project", project,
                "--pdf", str(pdf),
                "--paper-id", str(paper_id),
                "--model", model,
                "--prompt", f"multimodel gold-eval run: model={model}, paper_id={paper_id}",
            ]
            if args.dry_run:
                print("  $ " + " ".join(cmd))
                continue
            print(f"--- paper_id={paper_id}  {pdf.name} ---")
            env = {**os.environ, **PER_MODEL_ENV.get(model, {})}
            result = subprocess.run(cmd, cwd=_repo_root, env=env)
            if result.returncode != 0:
                failures.append((model, paper_id, pdf.name))

    if args.dry_run:
        print("\n(dry run -- nothing was called)")
        return 0

    print(f"\nDone. {len(failures)} failure(s).")
    for f in failures:
        print(f"  FAILED: model={f[0]} paper_id={f[1]} file={f[2]}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
