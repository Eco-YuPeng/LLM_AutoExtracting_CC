"""
literature_extractor.py — Core extraction library for cover crop PDFs.

Read this file before writing any workflow script (AGENTS.md step 1).
Do not modify it from workflows/ — add new logic in your workflow
script instead, importing what you need from here.

Implements AGENTS.md steps 1-12 / TASKS.md tasks 1-13. Pure-code stages
(PDF conversion, section location, deterministic extraction,
normalization rules, response-ratio math, row assembly) are fully
implemented. LLM-calling stages (classify_response_type,
extract_narrow_llm, extract_vision_llm, validate_with_apis) are stubs —
wire them to your model provider in the workflow script. Never fill
those in with a hardcoded guess; leaving them unimplemented and
skipping a paper is correct behavior until they're wired.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SCHEMA_PATH = _REPO_ROOT / "schema" / "cover_crop_schema.yml"
DEFAULT_CATALOG_PATH = _REPO_ROOT / "data_catalog.yml"


# ═══════════════════════════ Data classes ═══════════════════════════════

@dataclass
class PaperSpec:
    """One input PDF and what we know about it before processing."""
    pdf_path: Path
    paper_id: Optional[int] = None  # link to an article-level table, if one exists elsewhere


@dataclass
class ExtractedField:
    """One field's value plus its confidence and source note (AGENTS.md step 11)."""
    value: object
    confidence: str  # "high" | "medium" | "low"
    source: str       # short evidence note, e.g. "gazetteer match: Hairy vetch"
    method: str        # "regex" | "gazetteer" | "narrow_llm" | "vision_llm" | "computed_downstream"


@dataclass
class ExtractionWorkflow:
    """Configuration for one extraction run over one or more papers."""
    name: str
    papers: list[PaperSpec]
    schema_path: Path = DEFAULT_SCHEMA_PATH
    data_catalog_path: Path = DEFAULT_CATALOG_PATH
    output_dir: Optional[Path] = None
    verbose: bool = True


# ═══════════════════════════ Schema / catalog loading ════════════════════

def load_schema(schema_path: Path = DEFAULT_SCHEMA_PATH) -> dict:
    """Load and return the parsed schema.yml."""
    with open(schema_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_data_catalog(data_catalog_path: Path = DEFAULT_CATALOG_PATH) -> dict:
    """Load the species gazetteer + external validation API registry."""
    with open(data_catalog_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


# ═══════════════════════════ Step 1: PDF readability ══════════════════════

def check_pdf_readable(pdf_path: Path) -> tuple[bool, str]:
    """
    AGENTS.md step 1. Confirms the PDF opens and has an extractable text
    layer (not a scanned image with no OCR). Returns (ok, message).
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        return False, f"File not found: {pdf_path}"
    try:
        import fitz  # PyMuPDF
    except ImportError:
        return False, "PyMuPDF (fitz) not installed — run: pip install pymupdf"

    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        return False, f"Could not open PDF: {e}"

    if doc.page_count == 0:
        doc.close()
        return False, "PDF has zero pages"

    # Sample the first few pages for extractable text
    text_chars = 0
    for i in range(min(3, doc.page_count)):
        text_chars += len(doc[i].get_text().strip())
    doc.close()

    if text_chars < 50:
        return False, "No meaningful text layer found — likely a scanned image PDF with no OCR"

    return True, f"OK — {doc.page_count} pages, text layer present"


# ═══════════════════════════ Step 2: PDF → Markdown + identification ══════

DOI_PATTERN = re.compile(r"\b10\.\d{4,9}/\S+\b")


def pdf_to_markdown(pdf_path: Path) -> tuple[str, dict]:
    """
    AGENTS.md step 2. Converts the PDF to Markdown (preserving heading
    structure) and makes a best-effort identification pass on the same
    read: PDF metadata title/DOI, and a DOI-pattern regex scan of page 1.
    Never searches the web — if nothing is found, both identification
    values are None.

    Returns (markdown_text, identification) where identification has
    keys 'doi' and 'article_title'.
    """
    import fitz

    identification = {"doi": None, "article_title": None}

    doc = fitz.open(pdf_path)
    meta_title = (doc.metadata or {}).get("title") or None
    if meta_title and meta_title.strip() and meta_title.strip().lower() != "untitled":
        identification["article_title"] = meta_title.strip()

    page1_text = doc[0].get_text() if doc.page_count else ""
    doi_match = DOI_PATTERN.search(page1_text)
    if doi_match:
        identification["doi"] = doi_match.group(0).rstrip(".,;)")
    doc.close()

    try:
        import pymupdf4llm
        markdown_text = pymupdf4llm.to_markdown(str(pdf_path))
    except ImportError:
        raise ImportError(
            "pymupdf4llm not installed — run: pip install pymupdf4llm. "
            "This is the required PDF-to-markdown converter; do not "
            "substitute a full-document vision-LLM read instead."
        )

    return markdown_text, identification


# ═══════════════════════════ Step 3: Locate sections ══════════════════════

METHODS_HEADING_PATTERN = re.compile(
    r"^#{1,4}\s*\d{0,2}\.?\d{0,2}\.?\s*"
    r"(Materials?\s+an?d?\s+Methods?|Methods?|Materials?\s*&\s*Methods?|"
    r"Study\s+Site|Experimental\s+Design)\s*$",
    re.IGNORECASE | re.MULTILINE,
)

RESULTS_HEADING_PATTERN = re.compile(
    r"^#{1,4}\s*\d{0,2}\.?\d{0,2}\.?\s*"
    r"(Results(\s+an?d?\s+Discussion)?)\s*$",
    re.IGNORECASE | re.MULTILINE,
)

NEXT_TOPLEVEL_HEADING_PATTERN = re.compile(r"^#{1,2}\s+\S", re.MULTILINE)

ABSTRACT_HEADING_PATTERN = re.compile(r"^#{1,4}\s*Abstract\s*$", re.IGNORECASE | re.MULTILINE)


def _span_from_heading(text: str, heading_match: re.Match) -> str:
    """Everything from a matched heading to the next top-level heading."""
    start = heading_match.end()
    next_heading = NEXT_TOPLEVEL_HEADING_PATTERN.search(text, pos=start)
    end = next_heading.start() if next_heading else len(text)
    return text[start:end].strip()


def locate_sections(markdown_text: str) -> dict:
    """
    AGENTS.md step 3. Finds Methods and Results section spans by header
    matching. Falls back to Abstract, then full text, per TASKS.md Task 3.

    Returns {'methods': str|None, 'results': str|None,
    'fallback_used': str|None}. fallback_used is 'abstract' or
    'full_text' when no Methods heading was found — the caller must cap
    confidence at 'low' for any field extracted under 'full_text'.
    """
    methods_match = METHODS_HEADING_PATTERN.search(markdown_text)
    results_match = RESULTS_HEADING_PATTERN.search(markdown_text)

    methods_span = _span_from_heading(markdown_text, methods_match) if methods_match else None
    results_span = _span_from_heading(markdown_text, results_match) if results_match else None

    fallback_used = None
    if methods_span is None:
        abstract_match = ABSTRACT_HEADING_PATTERN.search(markdown_text)
        if abstract_match:
            methods_span = _span_from_heading(markdown_text, abstract_match)
            fallback_used = "abstract"
        else:
            methods_span = markdown_text
            fallback_used = "full_text"

    return {"methods": methods_span, "results": results_span, "fallback_used": fallback_used}


# ═══════════════════════════ Step 4: Deterministic extraction ═══════════

COORD_PATTERN = re.compile(
    r"(-?\d{1,3}\.\d+)\s*°?\s*[NnSs]?\s*[,;]?\s*(-?\d{1,3}\.\d+)\s*°?\s*[EeWw]?"
)

TILLAGE_KEYWORDS = {
    "no-till": "NT", "no till": "NT", "notill": "NT",
    "conventional tillage": "CT", "conventional till": "CT",
    "reduced till": "RT", "reduced-till": "RT", "reduced tillage": "RT",
}


def extract_deterministic(section_text: str, data_catalog: dict) -> dict[str, ExtractedField]:
    """
    AGENTS.md step 4. Regex + gazetteer only — zero LLM tokens. Covers
    schema fields tagged extraction_method: regex or gazetteer:
    latitude/longitude, cc_species/cc_species_scientific/cc_category,
    tillage. Extend this function as more deterministic fields are
    added, rather than pushing them into the narrow_llm stage.
    """
    fields: dict[str, ExtractedField] = {}

    coord_match = COORD_PATTERN.search(section_text)
    if coord_match:
        lat, lon = float(coord_match.group(1)), float(coord_match.group(2))
        if -90 <= lat <= 90 and -180 <= lon <= 180:
            fields["latitude"] = ExtractedField(lat, "high", "decimal-degree match in text", "regex")
            fields["longitude"] = ExtractedField(lon, "high", "decimal-degree match in text", "regex")

    for entry in data_catalog.get("species_gazetteer", []):
        names = [entry["scientific_name"], *entry.get("common_names", [])]
        for name in names:
            if re.search(re.escape(name), section_text, re.IGNORECASE):
                fields["cc_species"] = ExtractedField(name, "high", f"gazetteer match: {name}", "gazetteer")
                fields["cc_species_scientific"] = ExtractedField(
                    entry["scientific_name"], "high", "gazetteer lookup", "gazetteer"
                )
                fields["cc_category"] = ExtractedField(
                    entry["cc_category"], "high", "derived from species family in gazetteer", "gazetteer"
                )
                break
        if "cc_species" in fields:
            break

    for phrase, code in TILLAGE_KEYWORDS.items():
        if re.search(re.escape(phrase), section_text, re.IGNORECASE):
            fields["tillage"] = ExtractedField(code, "high", f"keyword match: '{phrase}'", "gazetteer")
            break

    return fields


# ═══════════════════════════ Step 5: Classify response type (LLM) ════════

RESPONSE_TYPE_OPTIONS = ["yield", "ghg_co2", "ghg_n2o", "ghg_ch4", "soc", "nitrogen"]


def classify_response_type(abstract_text: str, results_text: Optional[str]) -> ExtractedField:
    """
    AGENTS.md step 5. ONE cheap LLM call reading the abstract plus
    Results headers/captions. Must return a comma-separated subset of
    RESPONSE_TYPE_OPTIONS — a paper can hit more than one.

    STUB — wire this to your model provider in the workflow script.
    Do not default to a guessed category here; an unclassified paper
    should be logged and skipped, not assumed to be yield-only.
    """
    raise NotImplementedError(
        "classify_response_type: wire to your LLM provider in the workflow script. "
        f"Expected output: comma-separated subset of {RESPONSE_TYPE_OPTIONS}."
    )


# ═══════════════════════════ Step 6: Narrow LLM extraction ═══════════════

def extract_narrow_llm(section_text: str, field_names: list[str], schema: dict) -> dict[str, ExtractedField]:
    """
    AGENTS.md step 6. ONE consolidated LLM call scoped to section_text
    only — never the full paper. field_names must be exactly the schema
    fields with extraction_method: narrow_llm not already filled by
    extract_deterministic, for the relevant block.

    For multi-year studies, the call must map each numeric value in the
    Results text to a specific year using the same value-cross-
    referencing logic used in the Book4.xlsx year extraction — never
    assign a whole year-range to every row indiscriminately.

    STUB — wire this to your model provider in the workflow script.
    """
    raise NotImplementedError(
        "extract_narrow_llm: wire to your LLM provider in the workflow script. "
        f"Requested fields: {field_names}"
    )


# ═══════════════════════════ Step 7: Vision extraction (figures only) ════

def extract_vision_llm(pdf_path: Path, page_number: int, field_names: list[str]) -> dict[str, ExtractedField]:
    """
    AGENTS.md step 7. Only called when a Results value is explicitly
    figure-referenced (e.g. "as shown in Fig. 3") and
    extract_narrow_llm did not find it in text. Renders the given PDF
    page to an image (pure code — see render_page_to_image below), then
    makes ONE vision-capable LLM call scoped to that image.

    RULE: every ExtractedField returned here must have
    confidence="medium" unless the figure prints an explicit numeric
    data label (then "high" is allowed). Never default to "high".

    STUB — wire this to your model provider in the workflow script.
    """
    raise NotImplementedError(
        "extract_vision_llm: wire to your vision-capable model provider "
        f"in the workflow script. Page {page_number}, fields: {field_names}"
    )


def render_page_to_image(pdf_path: Path, page_number: int, output_path: Path, dpi: int = 200) -> Path:
    """
    Pure-code helper for step 7: renders one PDF page to a PNG. No LLM
    involved — call this before extract_vision_llm.
    """
    import fitz
    doc = fitz.open(pdf_path)
    if not (0 <= page_number < doc.page_count):
        doc.close()
        raise ValueError(f"page_number {page_number} out of range (0-{doc.page_count - 1})")
    page = doc[page_number]
    pix = page.get_pixmap(dpi=dpi)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pix.save(str(output_path))
    doc.close()
    return output_path


# ═══════════════════════════ Step 8: Normalize ═══════════════════════════

# Rule-based raw -> norm mappings. Extend as real raw values are
# encountered; only fall back to an LLM call (not implemented here) for
# text this table doesn't cover.
NORM_RULES: dict[str, dict[str, str]] = {
    "fertilize_norm": {"yes": "Yes", "no": "No", "0": "No"},
    "irrigation_norm": {
        "yes": "Irrigated", "irrrigated": "Irrigated", "irrigated": "Irrigated",
        "no": "Rainfed", "rainfall": "Rainfed", "null": "Unknown",
    },
}


def normalize_fields(extracted: dict[str, ExtractedField], schema: dict) -> dict[str, ExtractedField]:
    """
    AGENTS.md step 8. For every schema field with a _raw/_norm pair,
    produces the _norm value via NORM_RULES. Trims/lowercases for
    matching only — the stored _raw value is left untouched (see
    schema header: raw vs norm design principle).
    """
    normalized: dict[str, ExtractedField] = {}
    for norm_name, rule_table in NORM_RULES.items():
        raw_name = norm_name.replace("_norm", "_raw")
        if raw_name in extracted:
            raw_val = str(extracted[raw_name].value).strip().lower()
            if raw_val in rule_table:
                normalized[norm_name] = ExtractedField(
                    rule_table[raw_val], "high", f"rule match on raw value '{raw_val}'", "computed_downstream"
                )
    # grain_crop_norm: trim/case-fix only, no category remap needed
    if "grain_crop_raw" in extracted:
        cleaned = str(extracted["grain_crop_raw"].value).strip()
        if cleaned:
            normalized["grain_crop_norm"] = ExtractedField(
                cleaned, "high", "trimmed from grain_crop_raw", "computed_downstream"
            )
    return normalized


# ═══════════════════════════ Step 9: Response ratios (pure math) ═════════

RESPONSE_BLOCK_PREFIXES = ["yield_", "ghg_co2_", "ghg_n2o_", "ghg_ch4_", "soc_", "nitrogen_"]


def compute_response_ratios(row: dict[str, ExtractedField]) -> dict[str, ExtractedField]:
    """
    AGENTS.md step 9. Pure math, no LLM. For every Block 2 sub-block
    prefix with both {prefix}cc_mean and {prefix}control_mean present
    and positive, computes {prefix}ln_response_ratio =
    ln(cc_mean / control_mean). Variance fields (var_lnr and friends)
    are not computed here — wire the specific SD-based formula your
    meta-analysis uses (see schema.yml comments on the yield block's
    legacy multi-method variance fields) in the workflow script.
    """
    computed: dict[str, ExtractedField] = {}
    for prefix in RESPONSE_BLOCK_PREFIXES:
        cc_key, ctrl_key = f"{prefix}cc_mean", f"{prefix}control_mean"
        if cc_key in row and ctrl_key in row:
            cc_val, ctrl_val = row[cc_key].value, row[ctrl_key].value
            if cc_val is not None and ctrl_val is not None and cc_val > 0 and ctrl_val > 0:
                lnr = math.log(cc_val / ctrl_val)
                computed[f"{prefix}ln_response_ratio"] = ExtractedField(
                    lnr, "high", f"computed: ln({cc_key}/{ctrl_key})", "computed_downstream"
                )
    return computed


# ═══════════════════════════ Step 10: Validate ════════════════════════════

def validate_with_apis(row: dict[str, ExtractedField], data_catalog: dict) -> list[str]:
    """
    AGENTS.md step 10. Species-name and coordinate/country cross-checks
    against the external APIs in data_catalog.yml. Returns a list of
    flag messages for anything that didn't validate cleanly — an empty
    list means nothing was flagged (not that nothing was checked; check
    the flags list is genuinely populated in your implementation).

    STUB — the external_apis in data_catalog.yml are not reachable from
    a sandboxed chat container. Wire this in an environment with open
    network access (e.g. CyVerse).
    """
    raise NotImplementedError(
        "validate_with_apis: requires network access to GBIF/WFO/GeoNames/"
        "Nominatim (see data_catalog.yml) — not available in a sandboxed "
        "chat container. Run on CyVerse, or call these one at a time "
        "through the chat's own web_fetch tool for prototyping."
    )


# ═══════════════════════════ Step 11: Assemble row ════════════════════════

def assemble_row(paper: PaperSpec, all_fields: dict[str, ExtractedField], schema: dict) -> dict:
    """
    AGENTS.md step 11. Merges every stage's output into one row matching
    the schema's field order. Fields with status "dropped",
    "proposed_new", or "needs_confirmation" are never populated (see
    schema.yml open_questions — proposed_new fields wait for explicit
    user confirmation before the pipeline starts filling them). Any
    field not present in all_fields is left blank — never fabricated.
    """
    row: dict = {"pdf_path": str(paper.pdf_path), "paper_id": paper.paper_id}
    for category_fields in schema["fields"].values():
        for field_def in category_fields:
            name = field_def["name"]
            status = field_def.get("status")
            if status in ("dropped", "proposed_new", "needs_confirmation"):
                continue
            if name in all_fields:
                ef = all_fields[name]
                row[name] = ef.value
                if field_def.get("extraction_method") != "computed_downstream":
                    row[f"{name}_confidence"] = ef.confidence
                    row[f"{name}_source"] = ef.source
            else:
                row[name] = None
    return row


# ═══════════════════════════ Step 12: Orchestrator ════════════════════════

def run_extraction(workflow: ExtractionWorkflow) -> list[dict]:
    """
    Top-level orchestrator for AGENTS.md steps 1-4, 8-9, 11 (the
    pure-code stages). Steps 5-7 and 10 (LLM/vision/API calls) are
    NotImplementedError stubs above — a real workflow script wires
    those in per-paper before calling assemble_row, or subclasses this
    orchestration. One failed paper is logged and skipped; it never
    halts the batch (AGENTS.md: Failure Handling).
    """
    schema = load_schema(workflow.schema_path)
    data_catalog = load_data_catalog(workflow.data_catalog_path)
    rows: list[dict] = []

    for paper in workflow.papers:
        ok, msg = check_pdf_readable(paper.pdf_path)
        if not ok:
            if workflow.verbose:
                print(f"SKIP {paper.pdf_path}: {msg}")
            continue

        markdown_text, ident = pdf_to_markdown(paper.pdf_path)
        sections = locate_sections(markdown_text)

        all_fields: dict[str, ExtractedField] = {}
        if ident.get("doi"):
            all_fields["doi"] = ExtractedField(ident["doi"], "high", "regex match on PDF page 1", "regex")
        if ident.get("article_title"):
            all_fields["article_title"] = ExtractedField(
                ident["article_title"], "medium", "PDF metadata title field", "regex"
            )

        if sections["methods"]:
            all_fields.update(extract_deterministic(sections["methods"], data_catalog))
            # extract_narrow_llm(...) for the remaining Block 1 fields —
            # wire in your workflow script.

        # classify_response_type(...) then extract_narrow_llm(...) /
        # extract_vision_llm(...) for Block 2 — wire in your workflow
        # script; not called here since they require a model provider.

        all_fields.update(normalize_fields(all_fields, schema))
        all_fields.update(compute_response_ratios(all_fields))

        row = assemble_row(paper, all_fields, schema)
        if sections["fallback_used"] == "full_text" and workflow.verbose:
            print(f"NOTE {paper.pdf_path}: no Methods heading found, used full-text fallback — "
                  f"Block 1 fields on this row should be capped at low confidence.")
        rows.append(row)

    if workflow.output_dir:
        out_path = _write_output(rows, workflow.output_dir, workflow.name)
        if workflow.verbose:
            print(f"Wrote {len(rows)} row(s) to {out_path}")

    return rows


def _write_output(rows: list[dict], output_dir: Path, name: str) -> Path:
    """Append rows to workflows/<project>/output/<name>.csv."""
    import pandas as pd

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"{name}.csv"

    df = pd.DataFrame(rows)
    if out_path.exists():
        existing = pd.read_csv(out_path)
        df = pd.concat([existing, df], ignore_index=True)
    df.to_csv(out_path, index=False)
    return out_path
