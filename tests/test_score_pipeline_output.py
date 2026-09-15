"""Tests for ground_truth/scripts/score_pipeline_output.py -- synthetic
gold/pipeline rows, no real PDFs or LLM calls needed."""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "ground_truth" / "scripts"))
from score_pipeline_output import (  # noqa: E402
    score_row_pair, match_and_score, summarize, summarize_by_step, load_field_method_map,
    _precision_recall_f1,
)

FIELDS = ["country", "tillage_type_raw", "ghg_cc_mean", "gas_type"]


def test_score_row_pair_all_verdict_kinds():
    gold = {"country": "Japan", "tillage_type_raw": "nt", "ghg_cc_mean": 2.9, "gas_type": "n2o"}
    pipe = {"country": "Japan", "tillage_type_raw": "till", "ghg_cc_mean": None, "gas_type": "n2o"}
    v = score_row_pair(gold, pipe, FIELDS)
    assert v["country"] == "match"
    assert v["tillage_type_raw"] == "mismatch"
    assert v["ghg_cc_mean"] == "pipeline_missed"
    assert v["gas_type"] == "match"


def test_score_row_pair_both_blank_excluded_later():
    v = score_row_pair({"country": None}, {"country": None}, ["country"])
    assert v["country"] == "both_blank"


def test_score_row_pair_numeric_tolerance():
    v = score_row_pair({"ghg_cc_mean": 2.900001}, {"ghg_cc_mean": 2.9}, ["ghg_cc_mean"])
    assert v["ghg_cc_mean"] == "match"


def test_score_row_pair_no_pipeline_row_is_all_missed():
    v = score_row_pair({"country": "Japan", "ghg_cc_mean": 2.9}, {}, ["country", "ghg_cc_mean"])
    assert v["country"] == "pipeline_missed"
    assert v["ghg_cc_mean"] == "pipeline_missed"


def test_match_and_score_picks_best_matching_row_for_ambiguous_gas():
    # two pipeline rows for the same paper+gas -- the better match should win
    gold_df = pd.DataFrame([{"paper_id": 1, "gas_type": "n2o", "country": "Japan", "ghg_cc_mean": 2.9}])
    pipe_df = pd.DataFrame([
        {"paper_id": 1, "gas_type": "n2o", "country": "Japan", "ghg_cc_mean": 1.0},   # worse
        {"paper_id": 1, "gas_type": "n2o", "country": "Japan", "ghg_cc_mean": 2.9},   # better
    ])
    detail = match_and_score(gold_df, pipe_df, ["country", "ghg_cc_mean"])
    ghg_verdict = detail[detail["field"] == "ghg_cc_mean"]["verdict"].iloc[0]
    assert ghg_verdict == "match"


def test_match_and_score_missing_pipeline_paper_counts_as_missed():
    gold_df = pd.DataFrame([{"paper_id": 99, "gas_type": "n2o", "country": "Japan"}])
    pipe_df = pd.DataFrame([{"paper_id": 1, "gas_type": "n2o", "country": "USA"}])
    detail = match_and_score(gold_df, pipe_df, ["country"])
    assert (detail["verdict"] == "pipeline_missed").all()


def test_summarize_computes_accuracy_excluding_both_blank():
    detail = pd.DataFrame([
        {"field": "country", "verdict": "match"},
        {"field": "country", "verdict": "match"},
        {"field": "country", "verdict": "mismatch"},
        {"field": "country", "verdict": "both_blank"},  # excluded from denominator
    ])
    summary = summarize(detail, {"country": "narrow_llm"})
    row = summary.iloc[0]
    assert row["n_scored"] == 3
    assert row["n_match"] == 2
    assert abs(row["accuracy"] - 2 / 3) < 5e-4


def test_precision_recall_f1_helper():
    # all correct -> perfect on both
    p, r, f1 = _precision_recall_f1(tp=5, fp=0, fn=0)
    assert p == 1.0 and r == 1.0 and f1 == 1.0
    # nothing extracted, nothing expected -> both undefined (None), not zero
    assert _precision_recall_f1(tp=0, fp=0, fn=0) == (None, None, None)
    # all recall misses, no false positives -> precision undefined (no positive predictions at all)
    p, r, f1 = _precision_recall_f1(tp=0, fp=0, fn=4)
    assert p is None and r == 0.0 and f1 is None
    # all hallucinated, nothing was actually expected -> recall undefined
    p, r, f1 = _precision_recall_f1(tp=0, fp=4, fn=0)
    assert p == 0.0 and r is None and f1 is None


def test_summarize_precision_recall_asymmetric_within_one_field():
    # "location": 3 correct, 2 recall misses (pipeline_missed), 1 hallucination
    # (gold_blank_pipeline_filled) -- precision and recall must differ.
    detail = pd.DataFrame(
        [{"field": "location", "verdict": "match"}] * 3
        + [{"field": "location", "verdict": "pipeline_missed"}] * 2
        + [{"field": "location", "verdict": "gold_blank_pipeline_filled"}] * 1
    )
    summary = summarize(detail, {"location": "narrow_llm"})
    row = summary.iloc[0]
    assert row["n_scored"] == 6
    # tp=3, fp=1, fn=2 -- 5e-4 tolerance because summarize() rounds to 3 decimals
    assert abs(row["precision"] - 3 / 4) < 5e-4
    assert abs(row["recall"] - 3 / 5) < 5e-4
    assert row["precision"] != row["recall"]
    assert abs(row["f1"] - 2 * (3 / 4) * (3 / 5) / ((3 / 4) + (3 / 5))) < 5e-4


def test_summarize_by_step_groups_fields_by_pipeline_step():
    # "country" has only recall misses (pipeline_missed); "location" has only
    # precision misses (gold_blank_pipeline_filled) -- deliberately asymmetric
    # so the aggregate precision != aggregate recall, exercising the actual
    # P/R split rather than a case where they'd coincidentally be equal.
    field_summary = pd.DataFrame([
        {"field": "country", "pipeline_step": "6a/6b (narrow LLM)", "n_scored": 10, "n_match": 8,
         "n_mismatch": 0, "n_pipeline_missed": 2, "n_gold_blank_pipeline_filled": 0},
        {"field": "location", "pipeline_step": "6a/6b (narrow LLM)", "n_scored": 10, "n_match": 6,
         "n_mismatch": 0, "n_pipeline_missed": 0, "n_gold_blank_pipeline_filled": 4},
        {"field": "ghg_ln_response_ratio", "pipeline_step": "9/11 (pure computation)", "n_scored": 5, "n_match": 5,
         "n_mismatch": 0, "n_pipeline_missed": 0, "n_gold_blank_pipeline_filled": 0},
    ])
    step_summary = summarize_by_step(field_summary)
    llm_row = step_summary[step_summary["pipeline_step"] == "6a/6b (narrow LLM)"].iloc[0]
    assert llm_row["n_fields"] == 2
    assert llm_row["n_scored"] == 20
    assert llm_row["n_match"] == 14
    assert abs(llm_row["accuracy"] - 0.7) < 1e-9
    # tp=14, fp=4 (location's hallucinations), fn=2 (country's misses)
    # -- 5e-4 tolerance because summarize_by_step() rounds to 3 decimals
    assert abs(llm_row["precision"] - 14 / 18) < 5e-4
    assert abs(llm_row["recall"] - 14 / 16) < 5e-4
    assert llm_row["precision"] != llm_row["recall"]

    computed_row = step_summary[step_summary["pipeline_step"] == "9/11 (pure computation)"].iloc[0]
    assert computed_row["precision"] == 1.0
    assert computed_row["recall"] == 1.0


def test_load_field_method_map_covers_known_fields():
    m = load_field_method_map()
    assert m["country"] == "gazetteer"
    assert m["ghg_ln_response_ratio"] == "computed_downstream"
    assert m["cc_duration_years"] == "computed_downstream"
