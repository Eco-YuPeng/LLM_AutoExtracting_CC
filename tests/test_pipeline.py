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
    ExtractionWorkflow,
    PaperSpec,
    assemble_rows,
    classify_response_type,
    compute_cc_duration,
    compute_response_ratios,
    enumerate_experimental_units,
    extract_deterministic,
    extract_narrow_llm,
    find_species_candidates,
    group_response_types_by_block,
    load_data_catalog,
    load_schema,
    locate_sections,
    run_extraction,
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


def test_assemble_rows_site_specific_units_override_paper_wide_shared_fields():
    """Regression test: a paper with two physically distinct sites under
    different management (e.g. an unfertilized 'West site' vs. a
    conventionally-fertilized 'East site' both using glyphosate before
    planting) must produce one row per site with THAT site's own
    management values, not one row blending both sites together."""
    schema = load_schema()
    paper = PaperSpec(pdf_path=Path("x.pdf"), paper_id=1)
    # paper-wide fallback values (what a single-site paper would use as-is)
    shared = {
        "latitude": ExtractedField(46.99, "high", "regex", "regex"),
        "longitude": ExtractedField(-97.35, "high", "regex", "regex"),
        "fertilize_raw": ExtractedField("not fertilized", "medium", "blended guess", "narrow_llm"),
        "tillage_type_raw": ExtractedField("no-till", "high", "q", "narrow_llm"),
    }
    units = [
        {"location": ExtractedField("East site", "high", "q", "narrow_llm"),
         "fertilize_raw": ExtractedField("conventional; glyphosate pre-plant", "high", "q", "narrow_llm"),
         "cc_species": ExtractedField("Hairy vetch", "high", "q", "narrow_llm")},
        {"location": ExtractedField("West site", "high", "q", "narrow_llm"),
         "fertilize_raw": ExtractedField("not fertilized either year", "high", "q", "narrow_llm"),
         "cc_species": ExtractedField("Hairy vetch", "high", "q", "narrow_llm")},
    ]
    rows = assemble_rows(paper, shared, units, schema)
    assert len(rows) == 2
    assert rows[0]["location"] == "East site" and rows[1]["location"] == "West site"
    assert rows[0]["fertilize_raw"] == "conventional; glyphosate pre-plant"
    assert rows[1]["fertilize_raw"] == "not fertilized either year"
    # tillage wasn't overridden by either unit -> both rows fall back to the shared value
    assert rows[0]["tillage_type_raw"] == "no-till" and rows[1]["tillage_type_raw"] == "no-till"
    # both rows still share the same paper (same paper_id/pdf_path, same shared lat/lon) --
    # they are marked as the same article at two physical sites via paper_id + differing location
    assert rows[0]["paper_id"] == rows[1]["paper_id"] == 1
    assert rows[0]["pdf_path"] == rows[1]["pdf_path"] == "x.pdf"
    assert rows[0]["latitude"] == rows[1]["latitude"] == 46.99


def test_assemble_row_does_not_clobber_paper_id_with_none():
    """Regression test: paper_id is ALSO a schema field (status: active,
    extraction_method: manual_existing) that is never populated via
    all_fields (it comes from PaperSpec, e.g. --paper-id on the CLI) --
    the generic 'else: row[name] = None' schema loop must not stomp on
    the value already seeded from paper.paper_id."""
    schema = load_schema()
    paper = PaperSpec(pdf_path=Path("x.pdf"), paper_id=42)
    rows = assemble_rows(paper, {}, [], schema)
    assert rows[0]["paper_id"] == 42


def test_compute_cc_duration_counts_distinct_years():
    row = {"cc_years_practiced": ExtractedField("2016,2017", "high", "q", "narrow_llm")}
    out = compute_cc_duration(row)
    assert out["cc_duration_years"].value == 2


def test_compute_cc_duration_handles_non_contiguous_years():
    # duration = count of years actually practiced, not (max - min + 1)
    row = {"cc_years_practiced": ExtractedField("2016, 2018", "high", "q", "narrow_llm")}
    out = compute_cc_duration(row)
    assert out["cc_duration_years"].value == 2


def test_compute_cc_duration_absent_when_years_not_extracted():
    assert compute_cc_duration({}) == {}


def test_assemble_rows_computes_cc_duration_per_row():
    schema = load_schema()
    paper = PaperSpec(pdf_path=Path("x.pdf"))
    units = [{"cc_years_practiced": ExtractedField("2016,2017", "high", "q", "narrow_llm")}]
    rows = assemble_rows(paper, {}, units, schema, include_proposed=True)
    assert rows[0]["cc_duration_years"] == 2


def test_enumerate_units_mocked_carries_site_specific_fields_through(monkeypatch):
    """The parsing loop in enumerate_experimental_units is field-name-agnostic,
    so newly added SITE_VARIABLE_FIELDS (location, fertilize_raw, ...) and
    cc_years_practiced flow through untouched -- this pins that behavior."""
    schema = load_schema()
    fake = {"design_summary": "2 sites x 1 species x 1 gas",
            "units": [
                {"location": {"value": "West site", "confidence": "high", "evidence": "q"},
                 "fertilize_raw": {"value": "not fertilized", "confidence": "high", "evidence": "q"},
                 "cc_years_practiced": {"value": "2016,2017", "confidence": "high", "evidence": "q"},
                 "gas_type": {"value": "n2o", "confidence": "high", "evidence": "q"}},
            ]}
    monkeypatch.setattr(llm_client, "chat_json", lambda *a, **k: fake)
    units = enumerate_experimental_units("m", "r", [], ["ghg_n2o"], schema)
    assert len(units) == 1
    assert units[0]["location"].value == "West site"
    assert units[0]["fertilize_raw"].value == "not fertilized"
    assert units[0]["cc_years_practiced"].value == "2016,2017"


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


# ── enumerate_experimental_units: block-grouping + row-independence rules ──
# (methodology decisions from Yu Peng, 2026-09-14, added after a real
# gold-eval run truncated on a paper with response_types=['yield', 'nitrogen'])

def test_group_response_types_by_block_keeps_all_ghg_gases_together():
    # All three gases share one schema block ("ghg") -- they usually come
    # from the SAME results table, so they must stay in one group/call.
    groups = group_response_types_by_block(["ghg_co2", "ghg_n2o", "ghg_ch4"])
    assert groups == [["ghg_co2", "ghg_n2o", "ghg_ch4"]]


def test_group_response_types_by_block_splits_unrelated_blocks():
    # yield and nitrogen are different blocks/tables -- must become two
    # separate groups so neither call has to enumerate both at once.
    groups = group_response_types_by_block(["yield", "nitrogen"])
    assert groups == [["yield"], ["nitrogen"]]


def test_group_response_types_by_block_preserves_order_and_mixed_case():
    # yield, then both GHG gases together, then soc -- three groups, GHG's
    # two entries collapsed into one.
    groups = group_response_types_by_block(["yield", "ghg_n2o", "ghg_co2", "soc"])
    assert groups == [["yield"], ["ghg_n2o", "ghg_co2"], ["soc"]]


def test_group_response_types_by_block_empty_input():
    assert group_response_types_by_block([]) == []


def test_enumerate_units_prompt_states_independence_rule(monkeypatch):
    """The row-independence rule (a combination is only a row if RESULTS
    independently presents it, not merely described in Methods) must
    actually reach the model in the prompt text, not just live in a
    code comment."""
    schema = load_schema()
    captured = {}

    def fake_chat_json(system, user, *, purpose, cfg=None):
        captured["user"] = user
        return {"design_summary": "", "units": []}

    monkeypatch.setattr(llm_client, "chat_json", fake_chat_json)
    enumerate_experimental_units("m", "r", [], ["ghg_n2o"], schema)

    assert "INDEPENDENCE RULE" in captured["user"]
    assert "independently present" in captured["user"]


def test_enumerate_units_prompt_states_replication_is_not_a_factor(monkeypatch):
    schema = load_schema()
    captured = {}

    def fake_chat_json(system, user, *, purpose, cfg=None):
        captured["user"] = user
        return {"design_summary": "", "units": []}

    monkeypatch.setattr(llm_client, "chat_json", fake_chat_json)
    enumerate_experimental_units("m", "r", [], ["yield"], schema)
    assert "REPLICATION IS NOT A FACTOR" in captured["user"]


def test_enumerate_units_prompt_states_multi_year_average_rule(monkeypatch):
    schema = load_schema()
    captured = {}

    def fake_chat_json(system, user, *, purpose, cfg=None):
        captured["user"] = user
        return {"design_summary": "", "units": []}

    monkeypatch.setattr(llm_client, "chat_json", fake_chat_json)
    enumerate_experimental_units("m", "r", [], ["soc"], schema)
    assert "MULTI-YEAR AVERAGES" in captured["user"]


# ── locate_sections: Results also stops at a bare References heading ──────

def test_locate_sections_results_stops_at_references_when_no_discussion_heading():
    md = (
        "# Methods\nWe did methods things.\n\n"
        "# Results\nWe found results things.\n\n"
        "# References\nSmith 2020. Some paper.\n"
    )
    sections = locate_sections(md)
    assert "results things" in sections["results"]
    assert "Smith 2020" not in sections["results"]


def test_locate_sections_results_still_stops_at_discussion_when_present():
    # regression: adding References to the boundary pattern must not
    # break the existing Discussion/Conclusion boundary.
    md = (
        "# Methods\nWe did methods things.\n\n"
        "# Results\nWe found results things.\n\n"
        "# Discussion\nThis means X.\n\n"
        "# References\nSmith 2020.\n"
    )
    sections = locate_sections(md)
    assert "results things" in sections["results"]
    assert "This means X" not in sections["results"]
    assert "Smith 2020" not in sections["results"]


# ── enumerate_experimental_units: higher starting max_tokens floor ────────
# (real gold-eval evidence, 2026-09: this call's default 8000-token budget
# truncated on the FIRST attempt almost every time -- raise its own floor
# instead of the global default other, smaller calls rely on staying low)

def test_enumerate_units_raises_max_tokens_floor_when_default_is_low(monkeypatch):
    captured = {}

    def fake_chat_json(system, user, *, purpose, cfg=None):
        captured["cfg"] = cfg
        return {"design_summary": "", "units": []}

    monkeypatch.setattr(llm_client, "chat_json", fake_chat_json)
    schema = load_schema()
    low_cfg = llm_client.LLMConfig(api_key="fake", max_tokens=8000)
    enumerate_experimental_units("m", "r", [], ["yield"], schema, cfg=low_cfg)

    assert captured["cfg"].max_tokens == 16000
    assert low_cfg.max_tokens == 8000  # the caller's cfg object must not be mutated


def test_enumerate_units_keeps_caller_max_tokens_when_already_higher(monkeypatch):
    captured = {}

    def fake_chat_json(system, user, *, purpose, cfg=None):
        captured["cfg"] = cfg
        return {"design_summary": "", "units": []}

    monkeypatch.setattr(llm_client, "chat_json", fake_chat_json)
    schema = load_schema()
    high_cfg = llm_client.LLMConfig(api_key="fake", max_tokens=20000)
    enumerate_experimental_units("m", "r", [], ["yield"], schema, cfg=high_cfg)

    assert captured["cfg"].max_tokens == 20000  # left as-is, not lowered


# ── run_extraction: report.json must not crash when a paper yields zero
# rows and the output directory doesn't exist yet ─────────────────────────
# (real bug from a live gold-eval run, 2026-09: after `rm -rf
# workflows/<project>/`, the FIRST paper processed for a fresh project
# that fails outright -- e.g. a timed-out LLM call -- produced rows=[],
# and the report.json write below crashed with FileNotFoundError because
# only _write_output() (called only `if rows`) used to create the
# directory. That crash killed the whole run_extraction.py process
# instead of the graceful "log it, skip it, keep going" AGENTS.md
# promises for a single failed paper.)

def test_run_extraction_writes_report_json_when_output_dir_does_not_exist_yet(tmp_path):
    missing_pdf = tmp_path / "does_not_exist.pdf"  # check_pdf_readable() fails cleanly -> rows=[]
    fresh_output_dir = tmp_path / "brand_new_project" / "output"
    assert not fresh_output_dir.exists()

    wf = ExtractionWorkflow(name="t", papers=[PaperSpec(pdf_path=missing_pdf)],
                            output_dir=fresh_output_dir, verbose=False)
    rows = run_extraction(wf, use_llm=False)

    assert rows == []
    assert (fresh_output_dir / "t_report.json").exists()


def test_run_extraction_writes_report_json_after_a_paper_raises(tmp_path, monkeypatch):
    # Same bug, via the OTHER path to rows=[] -- extract_paper() itself
    # raising (e.g. an LLM call exhausting all retries), caught by
    # run_extraction()'s own try/except.
    import src.literature_extractor as le

    def boom(*a, **k):
        raise RuntimeError("simulated LLM failure after 4 retries")

    monkeypatch.setattr(le, "extract_paper", boom)
    fresh_output_dir = tmp_path / "another_new_project" / "output"

    wf = ExtractionWorkflow(name="t", papers=[PaperSpec(pdf_path=tmp_path / "x.pdf")],
                            output_dir=fresh_output_dir, verbose=False)
    rows = run_extraction(wf, use_llm=False)

    assert rows == []
    assert (fresh_output_dir / "t_report.json").exists()
