"""Smoke tests — verify the core library imports cleanly and the public API is intact."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_import_literature_extractor():
    from src.literature_extractor import (
        PaperSpec,
        ExtractionWorkflow,
        ExtractedField,
        load_schema,
        load_data_catalog,
        check_pdf_readable,
        pdf_to_markdown,
        locate_sections,
        extract_deterministic,
        classify_response_type,
        extract_narrow_llm,
        extract_vision_llm,
        normalize_fields,
        compute_response_ratios,
        validate_with_apis,
        assemble_row,
        run_extraction,
    )


def test_schema_loads_and_is_well_formed():
    from src.literature_extractor import load_schema

    schema = load_schema()
    assert "fields" in schema
    for category, field_list in schema["fields"].items():
        for field_def in field_list:
            assert "name" in field_def, f"field in {category} missing 'name'"
            assert "status" in field_def, f"{field_def.get('name')} missing 'status'"


def test_data_catalog_loads():
    from src.literature_extractor import load_data_catalog

    catalog = load_data_catalog()
    assert "species_gazetteer" in catalog
    assert len(catalog["species_gazetteer"]) > 0
    for entry in catalog["species_gazetteer"]:
        assert "scientific_name" in entry
        assert "cc_category" in entry


def test_locate_sections_finds_methods_heading():
    from src.literature_extractor import locate_sections

    md = "# Intro\ntext\n## Materials and Methods\nsite details here\n## Results\nvalues here"
    sections = locate_sections(md)
    assert sections["fallback_used"] is None
    assert "site details" in sections["methods"]


def test_locate_sections_handles_bold_numbered_same_level_subsections():
    """Regression test: a real paper (Franco et al. 2021, Agronomy
    Journal) renders headings as '## **2 MATERIALS AND METHODS**' with
    subsections '## **2.1 Site descriptions**' at the SAME markdown
    heading depth as the parent section. The naive "stop at next ##"
    approach cut the Methods span off almost immediately; it must
    instead run until the next section's own heading (Results)."""
    from src.literature_extractor import locate_sections

    md = (
        "## **2 MATERIALS AND METHODS** \n\n"
        "## **2.1 Site descriptions** \n\n"
        "This study was conducted near Mandan, ND (46.81˚ N, −100.92˚ W).\n\n"
        "## **2.2 Experimental design** \n\n"
        "More methods text here.\n\n"
        "## **3 RESULTS** \n\n"
        "## **3.1 Precipitation** \n\n"
        "Results text here.\n"
    )
    sections = locate_sections(md)
    assert sections["fallback_used"] is None
    assert "46.81" in sections["methods"]
    assert "Experimental design" in sections["methods"] or "More methods text" in sections["methods"]
    assert "RESULTS" not in sections["methods"]
    assert "Precipitation" in sections["results"]


def test_extract_deterministic_handles_unicode_degree_and_minus_signs():
    """Regression test: PDF text layers commonly use U+02DA (˚) instead
    of U+00B0 (°) for degree signs, and U+2212 (−) instead of ASCII '-'
    for negative coordinates — both must parse correctly."""
    from src.literature_extractor import extract_deterministic, load_data_catalog

    catalog = load_data_catalog()
    text = "This study was conducted near Mandan, ND (46.81˚ N, −100.92˚ W)."
    fields = extract_deterministic(text, catalog)
    assert fields["latitude"].value == 46.81
    assert fields["longitude"].value == -100.92


def test_compute_response_ratios():
    from src.literature_extractor import compute_response_ratios, ExtractedField
    import math

    row = {
        "yield_cc_mean": ExtractedField(5.5, "high", "test", "narrow_llm"),
        "yield_control_mean": ExtractedField(5.0, "high", "test", "narrow_llm"),
    }
    result = compute_response_ratios(row)
    assert "yield_ln_response_ratio" in result
    assert abs(result["yield_ln_response_ratio"].value - math.log(5.5 / 5.0)) < 1e-9
