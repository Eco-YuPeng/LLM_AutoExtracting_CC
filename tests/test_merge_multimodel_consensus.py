"""Tests for ground_truth/scripts/merge_multimodel_consensus.py -- synthetic
per-model rows, no real PDFs or LLM calls needed."""
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "ground_truth" / "scripts"))
from merge_multimodel_consensus import (  # noqa: E402
    consensus_for_field, build_consensus, summarize_agreement, parse_inputs, _representative_rows,
)


def test_consensus_for_field_majority_two_of_three():
    value, method, candidates = consensus_for_field({"a": "Japan", "b": "Japan", "c": "USA"})
    assert value == "Japan"
    assert method == "majority"
    assert candidates == {"a": "Japan", "b": "Japan", "c": "USA"}


def test_consensus_for_field_majority_uses_value_matching_not_exact_string():
    # 2.9 vs 2.900001 vs 2.9 -- two exact, one float-noisy but still "the same"
    value, method, _ = consensus_for_field({"a": 2.9, "b": 2.900001, "c": 5.0})
    assert method == "majority"
    assert value in (2.9, 2.900001)  # whichever cluster representative was first


def test_consensus_for_field_single_source():
    value, method, candidates = consensus_for_field({"a": "Japan", "b": None, "c": None})
    assert value == "Japan"
    assert method == "single_source"
    assert candidates == {"a": "Japan"}


def test_consensus_for_field_no_majority_all_disagree():
    value, method, candidates = consensus_for_field({"a": "Japan", "b": "USA", "c": "India"})
    assert value is None
    assert method == "no_majority"
    assert candidates == {"a": "Japan", "b": "USA", "c": "India"}


def test_consensus_for_field_all_blank():
    value, method, candidates = consensus_for_field({"a": None, "b": None, "c": float("nan")})
    assert value is None
    assert method == "all_blank"
    assert candidates == {}


def test_parse_inputs_requires_at_least_two(tmp_path):
    csv_a = tmp_path / "a.csv"
    csv_a.write_text("paper_id,gas_type\n1,n2o\n")
    with pytest.raises(SystemExit):
        parse_inputs([f"only_one={csv_a}"])


def test_parse_inputs_requires_equals_sign(tmp_path):
    csv_a = tmp_path / "a.csv"
    csv_a.write_text("paper_id,gas_type\n1,n2o\n")
    csv_b = tmp_path / "b.csv"
    csv_b.write_text("paper_id,gas_type\n1,n2o\n")
    with pytest.raises(SystemExit):
        parse_inputs([f"a{csv_a}", f"b={csv_b}"])


def test_representative_rows_takes_first_of_duplicate_group(tmp_path):
    df = pd.DataFrame([
        {"paper_id": 1, "gas_type": "n2o", "country": "Japan"},
        {"paper_id": 1, "gas_type": "n2o", "country": "SHOULD_NOT_WIN"},
        {"paper_id": 2, "gas_type": "co2", "country": "USA"},
    ])
    reps = _representative_rows(df)
    assert reps[(1, "n2o")]["country"] == "Japan"
    assert reps[(2, "co2")]["country"] == "USA"
    assert len(reps) == 2


def test_build_consensus_end_to_end():
    model_a = pd.DataFrame([{"paper_id": 1, "gas_type": "n2o", "country": "Japan", "tillage": "NT"}])
    model_b = pd.DataFrame([{"paper_id": 1, "gas_type": "n2o", "country": "Japan", "tillage": "CT"}])
    model_c = pd.DataFrame([{"paper_id": 1, "gas_type": "n2o", "country": "USA", "tillage": None}])
    inputs = {"a": model_a, "b": model_b, "c": model_c}
    consensus, detail = build_consensus(inputs, fields=["country", "tillage"])

    assert len(consensus) == 1
    row = consensus.iloc[0]
    assert row["country"] == "Japan"  # 2 of 3 agree
    assert pd.isna(row["tillage"])  # NT vs CT vs blank -- no majority

    country_detail = detail[(detail["field"] == "country")].iloc[0]
    assert country_detail["method"] == "majority"
    tillage_detail = detail[(detail["field"] == "tillage")].iloc[0]
    assert tillage_detail["method"] == "no_majority"


def test_build_consensus_unions_paper_groups_across_models():
    # model_a only saw paper 1, model_b only saw paper 2 -- both groups should
    # still appear in the merged output (each with whatever data exists).
    model_a = pd.DataFrame([{"paper_id": 1, "gas_type": "n2o", "country": "Japan"}])
    model_b = pd.DataFrame([{"paper_id": 2, "gas_type": "co2", "country": "USA"}])
    consensus, _ = build_consensus({"a": model_a, "b": model_b}, fields=["country"])
    assert set(zip(consensus["paper_id"], consensus["gas_type"])) == {(1, "n2o"), (2, "co2")}


def test_summarize_agreement_counts_methods_per_field():
    detail = pd.DataFrame([
        {"field": "country", "method": "majority"},
        {"field": "country", "method": "majority"},
        {"field": "country", "method": "no_majority"},
        {"field": "tillage", "method": "all_blank"},
    ])
    summary = summarize_agreement(detail).set_index("field")
    assert summary.loc["country", "n_majority"] == 2
    assert summary.loc["country", "n_no_majority"] == 1
    assert summary.loc["country", "pct_majority"] == pytest.approx(2 / 3, abs=1e-3)
    assert summary.loc["tillage", "n_all_blank"] == 1
