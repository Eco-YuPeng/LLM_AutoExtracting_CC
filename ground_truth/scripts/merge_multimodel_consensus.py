"""
Combine two or more models' extraction runs over the SAME set of papers
into one consensus CSV -- the "use N models, vote on the answer" step
Yu Peng asked for on top of the base eval loop.

Each --input is one model's full pipeline output CSV (same shape as
workflows/<project>/output/<project>.csv from run_extraction.py, one
model per run via LLM_MODEL). This script does NOT call any model itself
-- it only merges already-produced CSVs.

Row grouping: rows are grouped across all inputs by (paper_id, gas_type).
If a model produced more than one row for a group (e.g. two experimental
units both report n2o), only the FIRST is used as that model's
representative row for the group -- a documented simplification, same
spirit as score_pipeline_output.py's greedy row matching; multi-unit
papers should be revisited once the base loop is stable.

Per-field consensus, given the (up to N) models' values for a field in a
group, each compared with score_pipeline_output._values_match:
  - a value shared by >= 2 models (a "majority", not just any agreement)
    -> that value, method="majority"
  - exactly one model has a non-blank value, the rest are blank
    -> that value, method="single_source" (kept, but lower confidence --
       nothing to cross-check it against)
  - >= 2 non-blank values and no value is shared by >= 2 models
    -> blank, method="no_majority" (flagged for manual review; all
       candidate values are preserved in consensus_detail.csv)
  - every model is blank -> blank, method="all_blank"

Outputs (into --out-dir):
  consensus.csv                 schema-shaped, one row per (paper_id,
                                 gas_type), ready to feed straight into
                                 score_pipeline_output.py as --pipeline-csv
  consensus_detail.csv           long format: one row per
                                 (paper_id, gas_type, field) with the
                                 consensus value, the method, and every
                                 model's raw value -- for reviewing WHY a
                                 field is blank or disagreed on
  consensus_agreement_summary.csv  per field: how often models agreed vs
                                 split vs had only one source -- a second,
                                 independent signal from plain accuracy:
                                 a field with heavy no_majority is one the
                                 models can't reliably read at all,
                                 regardless of what the gold set says

Usage:
    python ground_truth/scripts/merge_multimodel_consensus.py \
        --input "gpt-oss-120b=workflows/gold_tier1_gptoss120b/output/gold_tier1_gptoss120b.csv" \
        --input "glm-5=workflows/gold_tier1_glm5/output/gold_tier1_glm5.csv" \
        --input "kimi=workflows/gold_tier1_kimi/output/gold_tier1_kimi.csv" \
        --out-dir ground_truth/output/consensus_run_<date>/
"""
import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from score_pipeline_output import _norm, _values_match, load_field_method_map, NEVER_SCORE  # noqa: E402

# Identity columns copied through as-is (not voted on) when present.
GROUP_KEYS = ["paper_id", "gas_type"]
PASSTHROUGH = {"paper_id", "gas_type", "pdf_path", "id", "data_source", "source_row_id"}


def parse_inputs(pairs: list[str]) -> dict[str, pd.DataFrame]:
    out = {}
    for pair in pairs:
        if "=" not in pair:
            raise SystemExit(f"--input must be NAME=PATH, got: {pair!r}")
        name, path = pair.split("=", 1)
        out[name] = pd.read_csv(path)
    if len(out) < 2:
        raise SystemExit("need at least 2 --input models to form a consensus")
    return out


def _representative_rows(df: pd.DataFrame) -> dict[tuple, dict]:
    """First row per (paper_id, gas_type) group, keyed by that tuple."""
    reps = {}
    if "paper_id" not in df.columns:
        return reps
    gas_col = df["gas_type"] if "gas_type" in df.columns else pd.Series([None] * len(df))
    for (paper_id, gas), group in df.assign(_gas=gas_col).groupby(["paper_id", "_gas"], dropna=False):
        reps[(paper_id, gas)] = group.iloc[0].to_dict()
    return reps


def consensus_for_field(values: dict[str, object]) -> tuple[object, str, dict[str, object]]:
    """values: {model_name: raw_value}. Returns (consensus_value, method, candidates).
    candidates is {model_name: raw_value} for every model with a non-blank value --
    always returned (even for majority/single_source) so consensus_detail.csv shows
    every model's answer, not just the winner."""
    non_blank = {m: v for m, v in values.items() if _norm(v) is not None}
    if not non_blank:
        return None, "all_blank", {}
    if len(non_blank) == 1:
        (only_model, only_val), = non_blank.items()
        return only_val, "single_source", non_blank

    # Cluster non-blank values by mutual agreement (_values_match), not just
    # exact string equality, so e.g. 2.900 and 2.9 count as the same vote.
    clusters: list[list[str]] = []  # list of model-name lists sharing a value
    rep_value: list[object] = []
    for model, val in non_blank.items():
        placed = False
        for ci, cluster in enumerate(clusters):
            if _values_match(rep_value[ci], val):
                cluster.append(model)
                placed = True
                break
        if not placed:
            clusters.append([model])
            rep_value.append(val)

    best_ci = max(range(len(clusters)), key=lambda i: len(clusters[i]))
    if len(clusters[best_ci]) >= 2:
        return rep_value[best_ci], "majority", non_blank
    return None, "no_majority", non_blank


def build_consensus(inputs: dict[str, pd.DataFrame], fields: list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    reps = {model: _representative_rows(df) for model, df in inputs.items()}
    all_keys = sorted({key for r in reps.values() for key in r.keys()},
                       key=lambda k: (str(k[0]), str(k[1])))

    consensus_rows, detail_rows = [], []
    for paper_id, gas in all_keys:
        row_out = {"paper_id": paper_id, "gas_type": gas}
        for field in fields:
            values = {}
            for model, rep in reps.items():
                r = rep.get((paper_id, gas))
                if r is not None and field in r:
                    values[model] = r[field]
            value, method, candidates = consensus_for_field(values)
            row_out[field] = value
            detail_rows.append({
                "paper_id": paper_id, "gas_type": gas, "field": field,
                "consensus_value": value, "method": method,
                **{f"model__{m}": v for m, v in candidates.items()},
            })
        consensus_rows.append(row_out)
    return pd.DataFrame(consensus_rows), pd.DataFrame(detail_rows)


def summarize_agreement(detail: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for field, g in detail.groupby("field"):
        n = len(g)
        rows.append({
            "field": field,
            "n_groups": n,
            "n_majority": (g["method"] == "majority").sum(),
            "n_single_source": (g["method"] == "single_source").sum(),
            "n_no_majority": (g["method"] == "no_majority").sum(),
            "n_all_blank": (g["method"] == "all_blank").sum(),
            "pct_majority": round((g["method"] == "majority").sum() / n, 3) if n else None,
        })
    return pd.DataFrame(rows).sort_values("pct_majority")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", action="append", required=True, help="NAME=PATH, repeat per model")
    ap.add_argument("--out-dir", required=True, type=Path)
    args = ap.parse_args()

    inputs = parse_inputs(args.input)
    field_method = load_field_method_map()
    all_columns = {c for df in inputs.values() for c in df.columns}
    fields = [f for f in all_columns
              if f in field_method and f not in NEVER_SCORE and f not in PASSTHROUGH
              and not f.startswith("extra__")]
    fields.sort()

    consensus, detail = build_consensus(inputs, fields)
    summary = summarize_agreement(detail)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    consensus.to_csv(args.out_dir / "consensus.csv", index=False)
    detail.to_csv(args.out_dir / "consensus_detail.csv", index=False)
    summary.to_csv(args.out_dir / "consensus_agreement_summary.csv", index=False)

    print(f"Merged {len(inputs)} models ({', '.join(inputs)}) over "
          f"{len(consensus)} (paper_id, gas_type) group(s), {len(fields)} fields.")
    print("\n=== Fields models agree on least (lowest %majority) ===")
    print(summary.head(10).to_string(index=False))
    print(f"\nWritten to {args.out_dir}/")


if __name__ == "__main__":
    main()
