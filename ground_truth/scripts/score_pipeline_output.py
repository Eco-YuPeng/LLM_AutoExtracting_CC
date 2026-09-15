"""
The scoring half of the eval loop:

    gold set -> run pipeline -> THIS SCRIPT (diff, attribute to a step)
    -> fix highest-impact error type -> full regression re-run -> repeat

Compares a real pipeline output CSV (from workflows/<project>/output/*.csv,
i.e. what run_extraction.py produces) against a gold-answer CSV built by
ground_truth/scripts/build_gold_eval_ghg_table.py, field by field, and
attributes every field to the AGENTS.md pipeline step that produces it
(via schema/cover_crop_schema.yml's extraction_method) -- so a low score
points at WHICH step to fix, not just THAT something is wrong.

Row matching: pipeline output is long-format (one row per gas per unit),
same as gold. Rows are grouped by paper_id, then matched by gas_type
within a paper; if a paper has more than one pipeline row for the same
gas_type (e.g. two units happen to both report n2o), each is scored
against the gold row and the best-matching one (fewest mismatches) is
kept -- a greedy heuristic, not an optimal assignment, but sufficient
for v1 and stated plainly here rather than silently approximated.

Metrics: alongside the original blended "accuracy" (n_match / n_scored,
kept for backward compat), each field/step also gets precision, recall,
and F1 -- borrowed from anthropic-skills:extract-from-pdfs's validation
methodology (2026-09-15, Yu Peng). A single accuracy number conflates two
very different failure modes that need different fixes: recall misses
("pipeline_missed" -- gold has a value, pipeline has nothing) point at an
upstream detection/classification gap, while precision misses
("gold_blank_pipeline_filled" -- pipeline invented a value gold says
shouldn't exist) point at an over-eager prompt. A "mismatch" (both
present, wrong value) costs both. Verdict -> (tp, fp, fn):
    match                        -> (1, 0, 0)
    mismatch                     -> (0, 1, 1)   -- wrong value hurts both
    pipeline_missed              -> (0, 0, 1)   -- recall miss
    gold_blank_pipeline_filled   -> (0, 1, 0)   -- precision miss
    both_blank                   -> excluded (true negative, nothing to score)
precision = tp/(tp+fp), recall = tp/(tp+fn), f1 = 2PR/(P+R).

Usage:
    python ground_truth/scripts/score_pipeline_output.py \\
        --pipeline-csv workflows/ghg_tier1_eval/output/ghg_tier1_eval.csv \\
        --gold-csv ground_truth/output/gold_eval_ghg_tier1.csv \\
        --out-dir ground_truth/output/scoring_run_<date>/
"""
import argparse
import sys
from pathlib import Path

import pandas as pd
import yaml

_repo_root = next(p for p in Path(__file__).resolve().parents
                   if (p / "schema" / "cover_crop_schema.yml").exists())
sys.path.insert(0, str(_repo_root))

SCHEMA_PATH = _repo_root / "schema" / "cover_crop_schema.yml"

# Which AGENTS.md step produces each extraction_method -- for grouping
# the report by "which step to go fix", not just "which field is wrong".
METHOD_TO_STEP = {
    "manual_existing": "0 (manual/identity, not extracted)",
    "regex": "4 (deterministic)",
    "gazetteer": "4 (deterministic)",
    "narrow_llm": "6a/6b (narrow LLM)",
    "vision_llm": "7 (vision LLM)",
    "computed_downstream": "9/11 (pure computation)",
}

# Fields that are identity/bookkeeping, not pipeline output -- never scored.
NEVER_SCORE = {"pdf_path", "paper_id", "id", "data_source", "source_row_id",
               "unit_index", "n_units_in_paper", "review_flags"}


def load_field_method_map() -> dict[str, str]:
    schema = yaml.safe_load(SCHEMA_PATH.read_text())
    out = {}
    for category_fields in schema["fields"].values():
        for field_def in category_fields:
            out[field_def["name"]] = field_def.get("extraction_method", "unknown")
    return out


def _norm(v):
    if pd.isna(v):
        return None
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    s = str(v).strip().lower()
    return s or None


def _values_match(a, b) -> bool:
    a, b = _norm(a), _norm(b)
    if a is None or b is None:
        return a is None and b is None
    try:
        fa, fb = float(a), float(b)
        return abs(fa - fb) <= max(1e-4, 1e-4 * max(abs(fa), abs(fb)))
    except (TypeError, ValueError):
        return a == b


def score_row_pair(gold_row: dict, pipe_row: dict, fields: list[str]) -> dict[str, str]:
    """Per-field verdict for one (gold, pipeline) row pair: 'match',
    'mismatch', 'gold_blank_pipeline_filled', 'pipeline_missed', or
    'both_blank' (both_blank is excluded from accuracy denominators --
    there was nothing to get right or wrong)."""
    verdicts = {}
    for f in fields:
        g, p = gold_row.get(f), pipe_row.get(f) if pipe_row else None
        g_blank, p_blank = _norm(g) is None, _norm(p) is None
        if g_blank and p_blank:
            verdicts[f] = "both_blank"
        elif g_blank and not p_blank:
            verdicts[f] = "gold_blank_pipeline_filled"
        elif not g_blank and p_blank:
            verdicts[f] = "pipeline_missed"
        elif _values_match(g, p):
            verdicts[f] = "match"
        else:
            verdicts[f] = "mismatch"
    return verdicts


_VERDICT_TP_FP_FN = {
    "match": (1, 0, 0),
    "mismatch": (0, 1, 1),
    "pipeline_missed": (0, 0, 1),
    "gold_blank_pipeline_filled": (0, 1, 0),
    # "both_blank" deliberately absent -- excluded from P/R, not a (0,0,0) count
}


def _precision_recall_f1(tp: int, fp: int, fn: int) -> tuple[float | None, float | None, float | None]:
    precision = tp / (tp + fp) if (tp + fp) else None
    recall = tp / (tp + fn) if (tp + fn) else None
    f1 = (2 * precision * recall / (precision + recall)
          if precision is not None and recall is not None and (precision + recall) > 0
          else None)
    return precision, recall, f1


def match_and_score(gold_df: pd.DataFrame, pipe_df: pd.DataFrame, fields: list[str]) -> pd.DataFrame:
    detail_rows = []
    for paper_id, gold_group in gold_df.groupby("paper_id"):
        pipe_group = pipe_df[pipe_df["paper_id"] == paper_id] if "paper_id" in pipe_df.columns else pipe_df.iloc[0:0]
        used_pipe_idx = set()
        for _, gold_row in gold_group.iterrows():
            gas = gold_row.get("gas_type")
            candidates = pipe_group[pipe_group.get("gas_type") == gas] if "gas_type" in pipe_group.columns else pipe_group
            candidates = candidates[~candidates.index.isin(used_pipe_idx)]
            best_verdicts, best_idx, best_score = None, None, -1
            for idx, cand_row in candidates.iterrows():
                verdicts = score_row_pair(gold_row.to_dict(), cand_row.to_dict(), fields)
                n_match = sum(v == "match" for v in verdicts.values())
                if n_match > best_score:
                    best_score, best_verdicts, best_idx = n_match, verdicts, idx
            if best_verdicts is None:
                # no pipeline row at all for this paper/gas -- everything gold
                # stated counts as pipeline_missed
                best_verdicts = score_row_pair(gold_row.to_dict(), {}, fields)
            else:
                used_pipe_idx.add(best_idx)
            for f, verdict in best_verdicts.items():
                detail_rows.append({
                    "paper_id": paper_id, "gas_type": gas,
                    "matched_pipeline_row": best_idx, "field": f, "verdict": verdict,
                })
    return pd.DataFrame(detail_rows)


def summarize(detail: pd.DataFrame, field_method: dict[str, str]) -> pd.DataFrame:
    rows = []
    for field, g in detail.groupby("field"):
        counted = g[g["verdict"] != "both_blank"]
        n = len(counted)
        n_match = (counted["verdict"] == "match").sum()
        tp = fp = fn = 0
        for verdict, contrib in _VERDICT_TP_FP_FN.items():
            count = (counted["verdict"] == verdict).sum()
            tp += count * contrib[0]
            fp += count * contrib[1]
            fn += count * contrib[2]
        precision, recall, f1 = _precision_recall_f1(tp, fp, fn)
        method = field_method.get(field, "unknown")
        rows.append({
            "field": field,
            "pipeline_step": METHOD_TO_STEP.get(method, method),
            "extraction_method": method,
            "n_scored": n,
            "n_match": n_match,
            "n_mismatch": (counted["verdict"] == "mismatch").sum(),
            "n_pipeline_missed": (counted["verdict"] == "pipeline_missed").sum(),
            "n_gold_blank_pipeline_filled": (counted["verdict"] == "gold_blank_pipeline_filled").sum(),
            "accuracy": round(n_match / n, 3) if n else None,
            "precision": round(precision, 3) if precision is not None else None,
            "recall": round(recall, 3) if recall is not None else None,
            "f1": round(f1, 3) if f1 is not None else None,
        })
    summary = pd.DataFrame(rows).sort_values(["accuracy", "n_scored"], ascending=[True, False])
    return summary


def summarize_by_step(field_summary: pd.DataFrame) -> pd.DataFrame:
    fs = field_summary.copy()
    fs["_tp"] = fs["n_match"]
    fs["_fp"] = fs["n_mismatch"] + fs["n_gold_blank_pipeline_filled"]
    fs["_fn"] = fs["n_mismatch"] + fs["n_pipeline_missed"]
    g = fs.groupby("pipeline_step").agg(
        n_fields=("field", "count"), n_scored=("n_scored", "sum"), n_match=("n_match", "sum"),
        tp=("_tp", "sum"), fp=("_fp", "sum"), fn=("_fn", "sum"),
    ).reset_index()
    g["accuracy"] = (g["n_match"] / g["n_scored"]).round(3)
    g["precision"] = (g["tp"] / (g["tp"] + g["fp"]).replace(0, pd.NA)).round(3)
    g["recall"] = (g["tp"] / (g["tp"] + g["fn"]).replace(0, pd.NA)).round(3)
    g["f1"] = (2 * g["precision"] * g["recall"] / (g["precision"] + g["recall"])).round(3)
    g = g.drop(columns=["tp", "fp", "fn"])
    return g.sort_values("accuracy")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pipeline-csv", required=True, type=Path)
    ap.add_argument("--gold-csv", required=True, type=Path)
    ap.add_argument("--out-dir", required=True, type=Path)
    args = ap.parse_args()

    gold_df = pd.read_csv(args.gold_csv)
    pipe_df = pd.read_csv(args.pipeline_csv)

    field_method = load_field_method_map()
    fields = [f for f in gold_df.columns
              if f in field_method and f not in NEVER_SCORE and not f.startswith("extra__")]

    detail = match_and_score(gold_df, pipe_df, fields)
    field_summary = summarize(detail, field_method)
    step_summary = summarize_by_step(field_summary)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    detail.to_csv(args.out_dir / "score_detail_by_row_field.csv", index=False)
    field_summary.to_csv(args.out_dir / "score_by_field.csv", index=False)
    step_summary.to_csv(args.out_dir / "score_by_pipeline_step.csv", index=False)

    print(f"Scored {gold_df['paper_id'].nunique()} papers, {len(gold_df)} gold rows, "
          f"{len(fields)} fields.")
    print("\n=== Accuracy by pipeline step (lowest first -- fix these) ===")
    print(step_summary.to_string(index=False))

    scored_fields = field_summary[field_summary["n_scored"] > 0]
    low_recall = scored_fields.sort_values("recall", na_position="first").head(10)
    low_precision = scored_fields.sort_values("precision", na_position="first").head(10)
    print("\n=== Worst 10 by RECALL (upstream detection/classification gap -- "
          "pipeline has nothing where gold has a value) ===")
    print(low_recall[["field", "pipeline_step", "n_scored", "n_pipeline_missed",
                      "recall", "precision", "f1"]].to_string(index=False))
    print("\n=== Worst 10 by PRECISION (over-eager extraction -- pipeline invents "
          "values gold says shouldn't exist, or gets present values wrong) ===")
    print(low_precision[["field", "pipeline_step", "n_scored", "n_gold_blank_pipeline_filled",
                         "n_mismatch", "precision", "recall", "f1"]].to_string(index=False))
    print(f"\nWorst 10 by accuracy (blended, for reference):"
          f"\n{field_summary.head(10).to_string(index=False)}")
    print(f"\nWritten to {args.out_dir}/")


if __name__ == "__main__":
    main()
