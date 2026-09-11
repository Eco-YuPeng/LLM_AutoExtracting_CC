"""Unit tests for the multi-row pipeline: species candidates, long-format
GHG, per-row response ratios, assemble_rows, and the LLM stages with the
model call mocked (no network, no key needed)."""

import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src import llm_client  # noqa: E402
from src.literature_extractor import (  # noqa: E402
    ExtractedField,
    PaperSpec,
    assemble_rows,
    classify_response_type,
    compute_response_ratios,
    enumerate_experimental_units,
    extract_deterministic,
    extract_narrow_llm,
    find_species_candidates,
    load_data_catalog,
    load_schema,
    sanity_check_row,
)


def test_ghg_schema_is_long_format():
    schema = load_schema()
    names = [f["name"] for f in schema["fields"]["ghg_data"]]
    assert "gas_type" in names
    assert "ghg_cc_mean" in names
    assert not any(n.startswith("ghg_co2_") for n in names)


def test_multiple_species_are_candidates_not_a_single_pick():
    catalog = load_data_catalog()
    text = ("Cover crop treatments were hairy vetch, cereal rye, and a rye + vetch mixture "
            "following soybean. Barley was grown in the previous rotation.")
    cands = find_species_candidates(text, catalog)
    matched = {c["matched_name"].lower() for c in cands}
    assert "hairy vetch" in matched
    assert len(cands) >= 2
    fields = extract_deterministic(text, catalog)
    assert "cc_species" not in fields  # ambiguous -> left to enumeration
    assert fields["cc_species_candidates"].value == cands


def test_single_species_is_assigned_deterministically():
    catalog = load_data_catalog()
    fields = extract_deterministic("The cover crop was hairy vetch, drilled in October.", catalog)
    assert fields["cc_species"].value.lower() == "hairy vetch"
    assert fields["cc_category"].value == "Legume"


def test_compute_response_ratios_ghg_long_format_with_variance():
    row = {
        "gas_type": ExtractedField("n2o", "high", "", "narrow_llm"),
        "ghg_cc_mean": ExtractedField(1.13, "high", "", "narrow_llm"),
        "ghg_control_mean": ExtractedField(1.43, "high", "", "narrow_llm"),
        "ghg_cc_sd": ExtractedField(0.2, "high", "", "narrow_llm"),
        "ghg_control_sd": ExtractedField(0.3, "high", "", "narrow_llm"),
        "ghg_n": ExtractedField(4, "high", "", "narrow_llm"),
    }
    out = compute_response_ratios(row)
    assert abs(out["ghg_ln_response_ratio"].value - math.log(1.13 / 1.43)) < 1e-9
    expected_var = 0.2 ** 2 / (4 * 1.13 ** 2) + 0.3 ** 2 / (4 * 1.43 ** 2)
    assert abs(out["ghg_var_lnr"].value - expected_var) < 1e-12


def test_assemble_rows_one_row_per_unit_sharing_block1():
    schema = load_schema()
    paper = PaperSpec(pdf_path=Path("x.pdf"), paper_id=1)
    shared = {
        "latitude": ExtractedField(46.81, "high", "regex", "regex"),
        "longitude": ExtractedField(-100.92, "high", "regex", "regex"),
        "tillage": ExtractedField("NT", "high", "kw", "gazetteer"),
        "irrigation_raw": ExtractedField("rainfed", "high", "q", "narrow_llm"),
    }
    units = [
        {"cc_species": ExtractedField("Hairy vetch", "high", "q", "narrow_llm"),
         "gas_type": ExtractedField("co2", "high", "q", "narrow_llm"),
         "ghg_cc_mean": ExtractedField(1.56, "high", "q", "narrow_llm"),
         "ghg_control_mean": ExtractedField(1.85, "high", "q", "narrow_llm")},
        {"cc_species": ExtractedField("Hairy vetch", "high", "q", "narrow_llm"),
         "gas_type": ExtractedField("n2o", "high", "q", "narrow_llm"),
         "ghg_cc_mean": ExtractedField(1.13, "high", "q", "narrow_llm"),
         "ghg_control_mean": ExtractedField(1.43, "high", "q", "narrow_llm")},
    ]
    rows = assemble_rows(paper, shared, units, schema)
    assert len(rows) == 2
    assert all(r["latitude"] == 46.81 and r["tillage"] == "NT" for r in rows)
    assert [r["gas_type"] for r in rows] == ["co2", "n2o"]
    assert abs(rows[1]["ghg_ln_response_ratio"] - math.log(1.13 / 1.43)) < 1e-9
    assert rows[0]["irrigation_norm"] == "Rainfed"
    assert rows[0]["unit_index"] == 1 and rows[1]["n_units_in_paper"] == 2
    assert "cc_species_candidates" not in rows[0]


def test_assemble_rows_with_no_units_keeps_one_row():
    schema = load_schema()
    rows = assemble_rows(PaperSpec(Path("x.pdf")), {"latitude": ExtractedField(1.0, "high", "", "regex")}, [], schema)
    assert len(rows) == 1 and rows[0]["latitude"] == 1.0


def test_sanity_check_flags_missing_gas_type():
    row = {"ghg_cc_mean": ExtractedField(1.0, "high", "", "narrow_llm")}
    assert any("gas_type" in f for f in sanity_check_row(row))


# ── LLM stages with the model mocked ─────────────────────────────────────

def test_classify_response_type_mocked(monkeypatch):
    monkeypatch.setattr(llm_client, "chat_json",
                        lambda *a, **k: {"response_types": ["yield", "ghg_n2o", "bogus"], "evidence": "Table 2"})
    ef = classify_response_type("abstract", "results")
    assert ef.value == "yield,ghg_n2o"
    assert ef.method == "narrow_llm"


def test_enumerate_units_mocked_drops_null_values(monkeypatch):
    schema = load_schema()
    fake = {"design_summary": "2 species x 1 gas",
            "units": [
                {"cc_species": {"value": "Cereal rye", "confidence": "high", "evidence": "q"},
                 "gas_type": {"value": "n2o", "confidence": "high", "evidence": "q"},
                 "ghg_cc_mean": {"value": 2.1, "confidence": "high", "evidence": "Table 3"},
                 "ghg_control_mean": {"value": None, "confidence": "low", "evidence": "Fig. 2"}},
            ]}
    monkeypatch.setattr(llm_client, "chat_json", lambda *a, **k: fake)
    units = enumerate_experimental_units("m", "r", [], ["ghg_n2o"], schema)
    assert len(units) == 1
    assert units[0]["ghg_cc_mean"].value == 2.1
    assert "ghg_control_mean" not in units[0]
    assert units[0]["_design_summary"].value == "2 species x 1 gas"


def test_extract_narrow_llm_mocked(monkeypatch):
    schema = load_schema()
    monkeypatch.setattr(llm_client, "chat_json",
                        lambda *a, **k: {"country": {"value": "USA", "confidence": "high", "evidence": "Mandan, ND"},
                                         "irrigation_raw": {"value": None}})
    out = extract_narrow_llm("methods", ["country", "irrigation_raw"], schema)
    assert out["country"].value == "USA" and "irrigation_raw" not in out


def test_llm_not_configured_raises(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(llm_client.LLMNotConfigured):
        llm_client.chat("s", "u", purpose="t", cfg=llm_client.LLMConfig(api_key=None))


def test_parse_json_response_tolerates_fences_and_prose():
    assert llm_client.parse_json_response('```json\n{"a": 1}\n```') == {"a": 1}
    assert llm_client.parse_json_response('Sure, here it is: {"a": [1,2]} thanks') == {"a": [1, 2]}


def test_parse_json_response_finds_real_json_after_inline_reasoning():
    """Regression test: some reasoning-model deployments (observed on
    nrp/glm-5 with thinking disabled via extra_body) put chain-of-thought
    directly in the answer content AHEAD OF the real JSON, including a
    JSON-shaped fragment quoted from the prompt itself — 'first { to
    last }' spans the prose between them and fails to parse. The real
    payload (last balanced block) must still be found."""
    messy = ('The user wants the capital of France. Return {"answer": "..."}\n\n'
            'I should return valid JSON only, as instructed.{"answer": "Paris"}')
    assert llm_client.parse_json_response(messy) == {"answer": "Paris"}


def test_parse_json_response_ignores_braces_inside_string_values():
    tricky = 'blah {"note": "curly brace example: {not real}"} trailing text'
    assert llm_client.parse_json_response(tricky) == {"note": "curly brace example: {not real}"}
