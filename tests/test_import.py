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
