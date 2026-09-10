"""
literature_extractor.py — Core extraction library for cover crop PDFs.

Read this file before writing any workflow script (AGENTS.md step 1).
Do not modify it from workflows/ — add new logic in your workflow
script instead, importing what you need from here.

Implements AGENTS.md steps 1-12. Pure-code stages (PDF conversion,
section location, deterministic extraction, normalization rules,
response-ratio math, row assembly) never touch a model. The judgment
stages (classify_response_type, enumerate_experimental_units,
extract_narrow_llm, extract_vision_llm) call the model through
src/llm_client.py (OpenAI-compatible endpoint, configured by
environment variables — see that module). A coding assistant driving
this repo (Roo Code, Claude Code, ...) runs these functions; it must
NOT substitute its own reading of the paper for their output.
validate_with_apis (external species/geo checks) is still a stub.
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
    page_count = doc.page_count
    text_chars = 0
    for i in range(min(3, page_count)):
        text_chars += len(doc[i].get_text().strip())
    doc.close()

    if text_chars < 50:
        return False, "No meaningful text layer found — likely a scanned image PDF with no OCR"

    return True, f"OK — {page_count} pages, text layer present"


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
    r"^#{1,4}\s*\**\s*(?:\d{1,2}\.?\s*)?"
    r"(Materials?\s+an?d?\s+Methods?|Methods?|Materials?\s*&\s*Methods?|"
    r"Study\s+Site|Experimental\s+Design)\s*\**\s*$",
    re.IGNORECASE | re.MULTILINE,
)

RESULTS_HEADING_PATTERN = re.compile(
    r"^#{1,4}\s*\**\s*(?:\d{1,2}\.?\s*)?"
    r"(Results(\s+an?d?\s+Discussion)?)\s*\**\s*$",
    re.IGNORECASE | re.MULTILINE,
)

# Bounds the far end of a Results section when no explicit next section
# is captured by RESULTS_HEADING_PATTERN's own match.
DISCUSSION_HEADING_PATTERN = re.compile(
    r"^#{1,4}\s*\**\s*(?:\d{1,2}\.?\s*)?"
    r"(Discussion|Conclusions?|Acknowledgy?ments?)\s*\**\s*$",
    re.IGNORECASE | re.MULTILINE,
)

NEXT_TOPLEVEL_HEADING_PATTERN = re.compile(r"^#{1,2}\s+\S", re.MULTILINE)

ABSTRACT_HEADING_PATTERN = re.compile(r"^#{1,4}\s*\**\s*Abstract\s*\**\s*$", re.IGNORECASE | re.MULTILINE)


def _span_from_heading(text: str, heading_match: re.Match, end_pattern: "re.Pattern | None" = None) -> str:
    """
    Everything from a matched heading to the next boundary.

    If end_pattern is given (e.g. Results' heading pattern bounding
    Methods, or Discussion's bounding Results), use its next match as
    the boundary, falling back to end-of-text if it isn't found —
    NEVER to "the next heading of any kind", since real papers often
    render subsection headings (e.g. "2.1 Site descriptions") at the
    SAME markdown heading depth as their parent section ("2 Materials
    and Methods"), which would cut the span off almost immediately.

    If no end_pattern is given at all (the Abstract fallback case,
    which has no natural "next known section" to bound it), fall back
    to the next heading of any kind — Abstracts are short and don't
    have this same-depth-subsection problem in practice.
    """
    start = heading_match.end()
    if end_pattern is not None:
        end_match = end_pattern.search(text, pos=start)
        end = end_match.start() if end_match else len(text)
        return text[start:end].strip()
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

    # Methods ends where Results begins (if found), not at the first
    # same-level subsection heading.
    methods_span = (
        _span_from_heading(markdown_text, methods_match, end_pattern=RESULTS_HEADING_PATTERN)
        if methods_match else None
    )
    # Results ends where Discussion/Conclusion begins (if found).
    results_span = (
        _span_from_heading(markdown_text, results_match, end_pattern=DISCUSSION_HEADING_PATTERN)
        if results_match else None
    )

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
    r"([−\-]?\d{1,3}\.\d+)\s*[°˚]?\s*([NnSs])?\s*[,;]?\s*"
    r"([−\-]?\d{1,3}\.\d+)\s*[°˚]?\s*([EeWw])?"
)


def _parse_coord(number_str: str, compass_letter: str | None, negative_letters: str) -> float:
    """
    Normalizes a coordinate number string (handling the Unicode minus
    sign U+2212 some PDF text layers use instead of ASCII '-') and
    applies the correct sign: negative if the text's own minus sign
    said so, OR if the compass letter (S/W) says so — never double-
    negate when a paper writes both (e.g. "-100.92 W").
    """
    normalized = number_str.replace("\u2212", "-")
    value = abs(float(normalized))
    is_negative_by_text = normalized.startswith("-")
    is_negative_by_letter = bool(compass_letter) and compass_letter.upper() in negative_letters
    return -value if (is_negative_by_text or is_negative_by_letter) else value

TILLAGE_KEYWORDS = {
    "no-till": "NT", "no till": "NT", "notill": "NT", "zero tillage": "NT", "zero-till": "NT",
    "conventional tillage": "CT", "conventional till": "CT", "moldboard": "CT", "mouldboard": "CT",
    "reduced till": "RT", "reduced-till": "RT", "reduced tillage": "RT", "minimum tillage": "RT",
    "strip-till": "RT", "strip till": "RT",
}

N_RATE_PATTERN = re.compile(r"(\d{1,3}(?:\.\d+)?)\s*kg\s*N\s*ha\s*[-−]?\s*1", re.IGNORECASE)


def find_species_candidates(section_text: str, data_catalog: dict) -> list[dict]:
    """
    Every gazetteer species mentioned anywhere in section_text, with the
    matched name and how many times it appears. This is an INTERMEDIATE
    signal for enumerate_experimental_units(), not a schema field: the
    gazetteer also contains crops that appear as cash crops or in
    rotations (barley, soybean, ...), so a mention is not proof that the
    species was used as a cover crop. The LLM enumeration step decides
    which candidates are actual cover-crop treatments, quoting the text.
    """
    candidates: list[dict] = []
    for entry in data_catalog.get("species_gazetteer", []):
        names = [entry["scientific_name"], *entry.get("common_names", [])]
        best_name, hits = None, 0
        for name in names:
            n = len(re.findall(r"\b" + re.escape(name) + r"\b", section_text, re.IGNORECASE))
            if n and (best_name is None or n > hits):
                best_name, hits = name, n
        if best_name:
            candidates.append({
                "matched_name": best_name,
                "scientific_name": entry["scientific_name"],
                "cc_category": entry["cc_category"],
                "family": entry.get("family"),
                "mentions": hits,
            })
    candidates.sort(key=lambda c: -c["mentions"])
    return candidates


def extract_deterministic(section_text: str, data_catalog: dict) -> dict[str, ExtractedField]:
    """
    AGENTS.md step 4. Regex + gazetteer only — zero LLM tokens. Covers
    schema fields tagged extraction_method: regex or gazetteer:
    latitude/longitude, tillage, cc_n_rate_kg_ha, and the species
    candidate list (stored under the non-schema key
    'cc_species_candidates'). cc_species itself is only set here when
    EXACTLY ONE gazetteer species occurs in the text — with several
    candidates the assignment is left to enumerate_experimental_units(),
    which reads the experimental design and can tell a cover crop from
    a cash crop or rotation partner.
    """
    fields: dict[str, ExtractedField] = {}

    coord_match = COORD_PATTERN.search(section_text)
    if coord_match:
        lat_str, lat_letter, lon_str, lon_letter = coord_match.groups()
        lat = _parse_coord(lat_str, lat_letter, negative_letters="S")
        lon = _parse_coord(lon_str, lon_letter, negative_letters="W")
        if -90 <= lat <= 90 and -180 <= lon <= 180:
            fields["latitude"] = ExtractedField(lat, "high", "decimal-degree match in text", "regex")
            fields["longitude"] = ExtractedField(lon, "high", "decimal-degree match in text", "regex")

    candidates = find_species_candidates(section_text, data_catalog)
    fields["cc_species_candidates"] = ExtractedField(
        candidates, "high", f"{len(candidates)} gazetteer species mentioned", "gazetteer"
    )
    if len(candidates) == 1:
        c = candidates[0]
        fields["cc_species"] = ExtractedField(c["matched_name"], "high", f"gazetteer match: {c['matched_name']} (only species in text)", "gazetteer")
        fields["cc_species_scientific"] = ExtractedField(c["scientific_name"], "high", "gazetteer lookup", "gazetteer")
        fields["cc_category"] = ExtractedField(c["cc_category"], "high", "derived from species family in gazetteer", "gazetteer")

    for phrase, code in TILLAGE_KEYWORDS.items():
        if re.search(re.escape(phrase), section_text, re.IGNORECASE):
            fields["tillage"] = ExtractedField(code, "high", f"keyword match: '{phrase}'", "gazetteer")
            break

    n_match = N_RATE_PATTERN.search(section_text)
    if n_match:
        fields["cc_n_rate_kg_ha"] = ExtractedField(
            float(n_match.group(1)), "medium", f"first 'kg N ha-1' figure in text: {n_match.group(0)!r} — confirm it refers to the cover crop", "regex"
        )

    return fields


# ═══════════════════════════ LLM prompt helpers ═══════════════════════════

_SYSTEM_BASE = (
    "You are a meticulous data-extraction assistant for an agricultural "
    "meta-analysis on cover crops. You only report what the supplied text "
    "states. You never guess, never fill gaps from general knowledge, and "
    "you always answer with valid JSON and nothing else. For every value "
    "you report, give a short verbatim quote from the text as evidence."
)


def _field_descriptions(schema: dict, field_names: list[str]) -> str:
    lookup = {f["name"]: f for fl in schema["fields"].values() for f in fl}
    lines = []
    for name in field_names:
        f = lookup.get(name, {})
        desc = " ".join(str(f.get("description", "")).split())
        vocab = f.get("controlled_vocabulary")
        line = f"- {name} ({f.get('type', 'string')}): {desc}"
        if vocab:
            line += f" Allowed values: {vocab}."
        lines.append(line)
    return "\n".join(lines)


def _to_extracted(obj: dict, default_method: str, cap: Optional[str] = None) -> Optional[ExtractedField]:
    """{'value':..,'confidence':..,'evidence':..} -> ExtractedField (None if value is null)."""
    if not isinstance(obj, dict) or obj.get("value") in (None, "", "null", "NA", "N/A"):
        return None
    conf = str(obj.get("confidence", "medium")).lower()
    if conf not in ("high", "medium", "low"):
        conf = "medium"
    if cap == "medium" and conf == "high":
        conf = "medium"
    return ExtractedField(obj["value"], conf, str(obj.get("evidence", ""))[:300], default_method)


def _truncate(text: Optional[str], max_chars: int) -> str:
    if not text:
        return ""
    return text if len(text) <= max_chars else text[:max_chars] + "\n[...truncated...]"


# ═══════════════════════════ Step 5: Classify response type (LLM) ════════

RESPONSE_TYPE_OPTIONS = ["yield", "ghg_co2", "ghg_n2o", "ghg_ch4", "soc", "nitrogen"]

# response type -> (schema sub-block, gas_type / nitrogen_type hint)
RESPONSE_TYPE_TO_BLOCK = {
    "yield": ("yield", None),
    "ghg_co2": ("ghg", "co2"),
    "ghg_n2o": ("ghg", "n2o"),
    "ghg_ch4": ("ghg", "ch4"),
    "soc": ("soc", None),
    "nitrogen": ("nitrogen", None),
}


def classify_response_type(abstract_text: str, results_text: Optional[str], cfg=None) -> ExtractedField:
    """
    AGENTS.md step 5. ONE cheap LLM call reading the abstract plus the
    first part of Results (headers/captions). Returns an ExtractedField
    whose value is a comma-separated subset of RESPONSE_TYPE_OPTIONS —
    a paper can hit more than one. An empty string means the paper
    reports none of the supported response types (log and skip it).
    """
    from src import llm_client

    user = (
        f"Supported response types: {RESPONSE_TYPE_OPTIONS}\n"
        "- yield: cash/grain crop yield compared between cover crop and no-cover-crop treatments\n"
        "- ghg_co2 / ghg_n2o / ghg_ch4: soil flux or cumulative emission of that gas\n"
        "- soc: soil organic carbon stock or concentration\n"
        "- nitrogen: soil mineral N, N leaching, or total soil N\n\n"
        "Which of these does the paper report with numeric cover-crop vs control comparisons? "
        "Only include a type if numbers for BOTH a cover crop treatment and a no-cover-crop control appear.\n\n"
        f"ABSTRACT:\n{_truncate(abstract_text, 6000)}\n\n"
        f"RESULTS (first part):\n{_truncate(results_text, 8000)}\n\n"
        'Answer as JSON: {"response_types": [...], "evidence": "<short quote(s)>"}'
    )
    data = llm_client.chat_json(_SYSTEM_BASE, user, purpose="classify_response_type", cfg=cfg)
    types = [t for t in data.get("response_types", []) if t in RESPONSE_TYPE_OPTIONS]
    return ExtractedField(",".join(types), "high" if types else "low",
                          str(data.get("evidence", ""))[:300], "narrow_llm")


# ═══════════════════════════ Step 6a: Enumerate experimental units (LLM) ══

UNIT_DESIGN_FIELDS = ["cc_species", "cc_species_scientific", "cc_type", "cc_category",
                      "year", "grain_crop_raw", "cc_planting_time_raw", "cc_terminating_time_raw",
                      "location"]


def enumerate_experimental_units(
    methods_text: str,
    results_text: Optional[str],
    species_candidates: list[dict],
    response_types: list[str],
    schema: dict,
    cfg=None,
) -> list[dict[str, ExtractedField]]:
    """
    AGENTS.md step 6a. ONE LLM call that turns a paper into the list of
    rows it should produce. One unit = one experimental-design
    combination (cover crop treatment/species x year x site ...) x one
    response variable (yield, one gas, SOC, one nitrogen metric).

    Returns a list of dicts of ExtractedField, each holding the design
    fields that differ between rows (cc_species, cc_type, year, ...) plus
    the Block 2 values for that unit's response variable
    ({prefix}cc_mean / {prefix}control_mean / _sd / _unit / _n and
    gas_type / nitrogen_type). Shared Block 1 fields are NOT repeated
    here — assemble_rows() merges them in.
    """
    from src import llm_client

    blocks = sorted({RESPONSE_TYPE_TO_BLOCK[t][0] for t in response_types if t in RESPONSE_TYPE_TO_BLOCK})
    gases = [RESPONSE_TYPE_TO_BLOCK[t][1] for t in response_types if t.startswith("ghg_")]

    value_fields = []
    for b in blocks:
        value_fields += [f"{b}_cc_mean", f"{b}_control_mean", f"{b}_cc_sd", f"{b}_control_sd", f"{b}_unit", f"{b}_n"]
        if b == "ghg":
            value_fields.append("gas_type")
        if b == "nitrogen":
            value_fields += ["nitrogen_type", "nitrogen_depth_cm"]
        if b == "soc":
            value_fields.append("soc_depth_cm")

    cand_txt = "\n".join(
        f"- {c['matched_name']} ({c['scientific_name']}, {c['cc_category']}, mentioned {c['mentions']}x)"
        for c in species_candidates
    ) or "- (none matched the gazetteer — read species names from the text)"

    user = (
        "TASK: enumerate every row this paper should contribute to a meta-analysis table.\n"
        "One row = one experimental-design combination (cover crop treatment or species, "
        "year or season, site, and any other factor the paper varies) x ONE response variable.\n"
        f"Response variables to enumerate: {response_types} "
        f"(GHG gases -> one row per gas: {gases or 'n/a'}).\n"
        "A mixture is ONE treatment (cc_species = the mixture's components joined by ' + ', cc_type = 'mixture').\n"
        "Only species used AS COVER CROPS are treatments. Cash crops, rotation partners, or "
        "species mentioned in the literature review are NOT rows.\n"
        "Every row must pair a cover-crop value with the matching no-cover-crop control value "
        "from the same year/site/factor level. If a value only appears in a figure, set it to "
        "null and put the figure reference (e.g. 'Fig. 3') in evidence.\n\n"
        f"Gazetteer species found in the text (hints only, decide from the design):\n{cand_txt}\n\n"
        f"Per-row fields to fill (null if the paper does not state it):\n"
        f"{_field_descriptions(schema, UNIT_DESIGN_FIELDS + value_fields)}\n\n"
        f"METHODS:\n{_truncate(methods_text, 30000)}\n\n"
        f"RESULTS:\n{_truncate(results_text, 30000)}\n\n"
        "Answer as JSON: {\"units\": [ {\"<field>\": {\"value\": ..., \"confidence\": \"high|medium|low\", "
        "\"evidence\": \"<verbatim quote or table/figure ref>\"}, ... }, ... ], "
        "\"design_summary\": \"<one sentence: factors x levels x years>\"}"
    )
    data = llm_client.chat_json(_SYSTEM_BASE, user, purpose="enumerate_experimental_units", cfg=cfg)

    units: list[dict[str, ExtractedField]] = []
    for raw_unit in data.get("units", []):
        unit: dict[str, ExtractedField] = {}
        for name, obj in raw_unit.items():
            ef = _to_extracted(obj, "narrow_llm")
            if ef is not None:
                unit[name] = ef
        if unit:
            unit["_design_summary"] = ExtractedField(data.get("design_summary", ""), "high", "", "narrow_llm")
            units.append(unit)
    return units


# ═══════════════════════════ Step 6b: Narrow LLM extraction ══════════════

def extract_narrow_llm(section_text: str, field_names: list[str], schema: dict, cfg=None) -> dict[str, ExtractedField]:
    """
    AGENTS.md step 6b. ONE consolidated LLM call scoped to section_text
    only — never the full paper. Used for the paper-level (shared) Block
    1 narrow_llm fields not filled by extract_deterministic — country,
    location, tillage_type_raw, fertilize_raw, irrigation_raw, soil
    texture, rotation, ccs_year_duration, etc.
    """
    from src import llm_client

    if not field_names:
        return {}
    user = (
        "Extract the following fields from the METHODS text of a cover crop field study. "
        "Report each value verbatim as the paper states it (these are *_raw fields; do not "
        "normalize). Use null when the text does not state it.\n\n"
        f"Fields:\n{_field_descriptions(schema, field_names)}\n\n"
        f"METHODS:\n{_truncate(section_text, 30000)}\n\n"
        "Answer as JSON: {\"<field>\": {\"value\": ..., \"confidence\": \"high|medium|low\", "
        "\"evidence\": \"<verbatim quote>\"}, ...}"
    )
    data = llm_client.chat_json(_SYSTEM_BASE, user, purpose="extract_narrow_llm", cfg=cfg)
    out: dict[str, ExtractedField] = {}
    for name in field_names:
        ef = _to_extracted(data.get(name), "narrow_llm")
        if ef is not None:
            out[name] = ef
    return out


# ═══════════════════════════ Step 7: Vision extraction (figures only) ════

def extract_vision_llm(pdf_path: Path, page_number: int, field_names: list[str],
                       context: str = "", cfg=None, image_dir: Optional[Path] = None) -> dict[str, ExtractedField]:
    """
    AGENTS.md step 7. Only called when a Results value is explicitly
    figure-referenced (e.g. "as shown in Fig. 3") and step 6 did not
    find it in text. Renders the given PDF page to an image (pure code)
    then makes ONE vision call scoped to that image.

    RULE: every ExtractedField returned here is capped at
    confidence="medium" unless the figure prints an explicit numeric
    data label (the model must say so via "data_label": true).
    """
    from src import llm_client

    image_dir = Path(image_dir) if image_dir else Path(pdf_path).parent / "_pages"
    png = render_page_to_image(Path(pdf_path), page_number, image_dir / f"{Path(pdf_path).stem}_p{page_number + 1}.png")
    user = (
        "Read the figure(s) on this page of a cover crop paper and report the requested values. "
        "If a value must be estimated from bar/point height rather than a printed number, say so "
        "(data_label=false). Use null when the figure does not show it.\n"
        f"Context: {context}\n\n"
        f"Fields: {field_names}\n\n"
        "Answer as JSON: {\"<field>\": {\"value\": ..., \"confidence\": \"high|medium|low\", "
        "\"evidence\": \"<panel / axis / legend read>\", \"data_label\": true|false}, ...}"
    )
    data = llm_client.chat_json(_SYSTEM_BASE, user, purpose="extract_vision_llm", cfg=cfg, image_png_path=png)
    out: dict[str, ExtractedField] = {}
    for name in field_names:
        obj = data.get(name)
        cap = None if (isinstance(obj, dict) and obj.get("data_label") is True) else "medium"
        ef = _to_extracted(obj, "vision_llm", cap=cap)
        if ef is not None:
            out[name] = ef
    return out


def render_page_to_image(pdf_path: Path, page_number: int, output_path: Path, dpi: int = 200) -> Path:
    """
    Pure-code helper for step 7: renders one PDF page to a PNG. No LLM
    involved — call this before extract_vision_llm.
    """
    import fitz
    doc = fitz.open(pdf_path)
    page_count = doc.page_count
    if not (0 <= page_number < page_count):
        doc.close()
        raise ValueError(f"page_number {page_number} out of range (0-{page_count - 1})")
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
    "fertilize_norm": {"yes": "Yes", "no": "No", "0": "No", "none": "No", "fertilized": "Yes", "unfertilized": "No"},
    "irrigation_norm": {
        "yes": "Irrigated", "irrrigated": "Irrigated", "irrigated": "Irrigated",
        "no": "Rainfed", "rainfall": "Rainfed", "rainfed": "Rainfed", "rain-fed": "Rainfed",
        "null": "Unknown", "none": "Rainfed",
    },
    "herbicide_norm": {"yes": "Yes", "no": "No", "none": "No", "glyphosate": "Yes"},
    "tillage_type_norm": {
        "no-till": "NT", "no till": "NT", "nt": "NT", "zero tillage": "NT",
        "conventional tillage": "CT", "conventional": "CT", "ct": "CT", "moldboard plow": "CT",
        "reduced tillage": "RT", "reduced": "RT", "rt": "RT", "minimum tillage": "RT", "strip-till": "RT",
    },
}


def normalize_fields(extracted: dict[str, ExtractedField], schema: dict) -> dict[str, ExtractedField]:
    """
    AGENTS.md step 8. For every schema field with a _raw/_norm pair,
    produces the _norm value via NORM_RULES. Trims/lowercases for
    matching only — the stored _raw value is left untouched (see
    schema header: raw vs norm design principle). Runs per ROW.
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
    for raw_name, norm_name in (("grain_crop_raw", "grain_crop_norm"),
                                ("cc_rotation_raw", "cc_rotation_norm"),
                                ("grain_crop_rotation_raw", "grain_crop_rotation_norm"),
                                ("soil_texture_raw", "soil_texture_norm")):
        if raw_name in extracted and norm_name not in normalized:
            cleaned = str(extracted[raw_name].value).strip()
            if cleaned:
                normalized[norm_name] = ExtractedField(cleaned, "medium", f"trimmed from {raw_name} (no vocabulary rule yet)", "computed_downstream")
    return normalized


# ═══════════════════════════ Step 9: Response ratios (pure math) ═════════

RESPONSE_BLOCK_PREFIXES = ["yield_", "ghg_", "soc_", "nitrogen_"]


def _num(x) -> Optional[float]:
    try:
        v = float(x)
        return v if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None


def compute_response_ratios(row: dict[str, ExtractedField]) -> dict[str, ExtractedField]:
    """
    AGENTS.md step 9. Pure math, no LLM, per ROW. For every Block 2
    sub-block prefix with both {prefix}cc_mean and {prefix}control_mean
    present and positive: ln_response_ratio = ln(cc/control). When both
    SDs and n are also present: var_lnr = sd_cc^2/(n*cc^2) +
    sd_ctrl^2/(n*ctrl^2) (Hedges et al. 1999, equal n). The legacy yield
    variants (var_lnr_uniformed / _harmonic_n / _all_ave) are NOT
    computed here — they depend on the SD-imputation history of the
    source file and belong to the downstream stats script.
    """
    computed: dict[str, ExtractedField] = {}
    for prefix in RESPONSE_BLOCK_PREFIXES:
        cc = _num(row[f"{prefix}cc_mean"].value) if f"{prefix}cc_mean" in row else None
        ctrl = _num(row[f"{prefix}control_mean"].value) if f"{prefix}control_mean" in row else None
        if cc is None or ctrl is None or cc <= 0 or ctrl <= 0:
            continue
        computed[f"{prefix}ln_response_ratio"] = ExtractedField(
            math.log(cc / ctrl), "high", f"computed: ln({prefix}cc_mean/{prefix}control_mean)", "computed_downstream"
        )
        if prefix == "yield_":
            continue
        sd_cc = _num(row[f"{prefix}cc_sd"].value) if f"{prefix}cc_sd" in row else None
        sd_ct = _num(row[f"{prefix}control_sd"].value) if f"{prefix}control_sd" in row else None
        n = _num(row[f"{prefix}n"].value) if f"{prefix}n" in row else None
        if sd_cc is not None and sd_ct is not None and n and n > 0:
            var = sd_cc ** 2 / (n * cc ** 2) + sd_ct ** 2 / (n * ctrl ** 2)
            computed[f"{prefix}var_lnr"] = ExtractedField(var, "high", "computed: Hedges lnRR variance, equal n", "computed_downstream")
    return computed


# ═══════════════════════════ Step 10: Validate ════════════════════════════

def validate_with_apis(row: dict[str, ExtractedField], data_catalog: dict) -> list[str]:
    """
    AGENTS.md step 10. Species-name and coordinate/country cross-checks
    against the external APIs in data_catalog.yml. Returns a list of
    flag messages for anything that didn't validate cleanly.

    STUB — external validation is wired in a later task. Until then,
    sanity_check_row() below provides the offline numeric checks.
    """
    raise NotImplementedError(
        "validate_with_apis: requires network access to GBIF/WFO/GeoNames/"
        "Nominatim (see data_catalog.yml). Not yet wired — use sanity_check_row()."
    )


def sanity_check_row(row: dict[str, ExtractedField]) -> list[str]:
    """Offline numeric / consistency checks for one row. Returns flags."""
    flags: list[str] = []
    lat = _num(row["latitude"].value) if "latitude" in row else None
    lon = _num(row["longitude"].value) if "longitude" in row else None
    if lat is not None and not -90 <= lat <= 90:
        flags.append(f"latitude out of range: {lat}")
    if lon is not None and not -180 <= lon <= 180:
        flags.append(f"longitude out of range: {lon}")
    for prefix in RESPONSE_BLOCK_PREFIXES:
        for side in ("cc", "control"):
            m = _num(row[f"{prefix}{side}_mean"].value) if f"{prefix}{side}_mean" in row else None
            sd = _num(row[f"{prefix}{side}_sd"].value) if f"{prefix}{side}_sd" in row else None
            if m is not None and sd is not None and sd > 3 * abs(m) and m != 0:
                flags.append(f"{prefix}{side}_sd ({sd}) > 3x mean ({m}) — check units / SE vs SD")
            if prefix == "yield_" and m is not None and m < 0:
                flags.append(f"negative yield: {prefix}{side}_mean={m}")
    if "gas_type" in row and str(row["gas_type"].value).lower() not in ("co2", "n2o", "ch4"):
        flags.append(f"gas_type not in vocabulary: {row['gas_type'].value}")
    if any(k.startswith("ghg_") and k.endswith("_mean") for k in row) and "gas_type" not in row:
        flags.append("ghg values present but gas_type missing")
    return flags


# ═══════════════════════════ Step 11: Assemble rows ═══════════════════════

_SKIP_STATUS = ("dropped", "proposed_new", "needs_confirmation")


def assemble_row(paper: PaperSpec, all_fields: dict[str, ExtractedField], schema: dict,
                 include_proposed: bool = False, extra: Optional[dict] = None) -> dict:
    """
    AGENTS.md step 11 (single row). Merges every stage's output into one
    row matching the schema's field order. Fields with status "dropped",
    "proposed_new" (unless include_proposed=True), or
    "needs_confirmation" are never populated. Any field not present in
    all_fields is left blank — never fabricated. Internal keys (leading
    underscore, or *_candidates) are never written.
    """
    row: dict = {"pdf_path": str(paper.pdf_path), "paper_id": paper.paper_id}
    row.update(extra or {})
    for category_fields in schema["fields"].values():
        for field_def in category_fields:
            name = field_def["name"]
            status = field_def.get("status")
            if status in _SKIP_STATUS and not (include_proposed and status == "proposed_new"):
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


def assemble_rows(paper: PaperSpec, shared_fields: dict[str, ExtractedField],
                  units: list[dict[str, ExtractedField]], schema: dict,
                  include_proposed: bool = False) -> list[dict]:
    """
    AGENTS.md step 11 (multi-row). shared_fields = paper-level Block 1
    values (coordinates, country, tillage, ...). units = output of
    enumerate_experimental_units(). For each unit: merge shared + unit
    (unit wins on conflict), run normalize_fields() and
    compute_response_ratios() per row, then assemble. With an empty
    units list one row with the shared fields only is produced, so a
    paper is never silently lost.
    """
    rows: list[dict] = []
    unit_list = units or [{}]
    for i, unit in enumerate(unit_list, start=1):
        merged: dict[str, ExtractedField] = {**shared_fields, **{k: v for k, v in unit.items() if not k.startswith("_")}}
        merged.update(normalize_fields(merged, schema))
        merged.update(compute_response_ratios(merged))
        flags = sanity_check_row(merged)
        extra = {"unit_index": i, "n_units_in_paper": len(unit_list), "review_flags": "; ".join(flags) or None}
        rows.append(assemble_row(paper, merged, schema, include_proposed=include_proposed, extra=extra))
    return rows


# ═══════════════════════════ Step 12: Orchestrator ════════════════════════

SHARED_NARROW_FIELDS = [
    "country", "location", "ccs_year_duration", "cc_rotation_raw", "grain_crop_rotation_raw",
    "tillage_type_raw", "fertilize_raw", "grain_crop_n_rate_raw", "herbicide_raw", "irrigation_raw",
    "soil_texture_raw", "annual_precipitation_mm", "annual_temperature_c", "notes",
]


def extract_paper(paper: PaperSpec, schema: dict, data_catalog: dict, *, use_llm: bool = True,
                  include_proposed: bool = False, cfg=None, verbose: bool = True) -> tuple[list[dict], dict]:
    """
    Runs steps 1-11 for ONE paper and returns (rows, report). report
    holds the intermediate signals (sections found, species candidates,
    response types, design summary, LLM call log slice) for the
    PROMPT_ACTION_LOG entry and for human review.
    """
    from src import llm_client

    report: dict = {"pdf": str(paper.pdf_path), "status": "ok", "notes": []}
    ok, msg = check_pdf_readable(paper.pdf_path)
    if not ok:
        report.update(status="skipped", notes=[msg])
        return [], report

    markdown_text, ident = pdf_to_markdown(paper.pdf_path)
    sections = locate_sections(markdown_text)
    report["fallback_used"] = sections["fallback_used"]
    report["methods_chars"] = len(sections["methods"] or "")
    report["results_chars"] = len(sections["results"] or "")

    shared: dict[str, ExtractedField] = {}
    if ident.get("doi"):
        shared["doi"] = ExtractedField(ident["doi"], "high", "regex match on PDF page 1", "regex")
    if ident.get("article_title"):
        shared["article_title"] = ExtractedField(ident["article_title"], "medium", "PDF metadata title field", "regex")

    methods_text = sections["methods"] or ""
    shared.update(extract_deterministic(methods_text, data_catalog))
    candidates = shared.pop("cc_species_candidates").value
    report["species_candidates"] = candidates

    if sections["fallback_used"] == "full_text":
        for ef in shared.values():
            ef.confidence = "low"
        report["notes"].append("no Methods heading found — full-text fallback, Block 1 capped at low")

    units: list[dict[str, ExtractedField]] = []
    if use_llm:
        log_start = len(llm_client.CALL_LOG)
        abstract_match = ABSTRACT_HEADING_PATTERN.search(markdown_text)
        abstract_text = _span_from_heading(markdown_text, abstract_match) if abstract_match else markdown_text[:4000]

        rt = classify_response_type(abstract_text, sections["results"], cfg=cfg)
        shared["response_types_detected"] = rt
        response_types = [t for t in rt.value.split(",") if t]
        report["response_types"] = response_types

        missing = [f for f in SHARED_NARROW_FIELDS if f not in shared]
        shared.update(extract_narrow_llm(methods_text, missing, schema, cfg=cfg))

        if response_types:
            units = enumerate_experimental_units(methods_text, sections["results"], candidates,
                                                 response_types, schema, cfg=cfg)
            if units:
                report["design_summary"] = units[0].get("_design_summary", ExtractedField("", "", "", "")).value
        else:
            report["notes"].append("no supported response type detected — Block 2 left blank")
        report["llm_calls"] = llm_client.CALL_LOG[log_start:]
    else:
        report["notes"].append("use_llm=False — only deterministic fields extracted")

    rows = assemble_rows(paper, shared, units, schema, include_proposed=include_proposed)
    report["n_rows"] = len(rows)
    if verbose:
        print(f"{Path(paper.pdf_path).name}: {len(rows)} row(s); response_types={report.get('response_types')}; "
              f"candidates={[c['matched_name'] for c in candidates]}")
    return rows, report


def run_extraction(workflow: ExtractionWorkflow, *, use_llm: bool = True,
                   include_proposed: bool = False, cfg=None) -> list[dict]:
    """
    Top-level orchestrator: extract_paper() for every PaperSpec, then
    write. One failed paper is logged and skipped; it never halts the
    batch (AGENTS.md: Failure Handling). Reports are written next to the
    CSV as <name>_report.json.
    """
    import json

    schema = load_schema(workflow.schema_path)
    data_catalog = load_data_catalog(workflow.data_catalog_path)
    rows: list[dict] = []
    reports: list[dict] = []

    for paper in workflow.papers:
        try:
            paper_rows, report = extract_paper(paper, schema, data_catalog, use_llm=use_llm,
                                               include_proposed=include_proposed, cfg=cfg,
                                               verbose=workflow.verbose)
        except Exception as e:  # noqa: BLE001 — never halt the batch
            report = {"pdf": str(paper.pdf_path), "status": "failed", "notes": [repr(e)[:500]]}
            paper_rows = []
            if workflow.verbose:
                print(f"FAILED {paper.pdf_path}: {e!r}")
        rows.extend(paper_rows)
        reports.append(report)

    if workflow.output_dir:
        out_path = _write_output(rows, workflow.output_dir, workflow.name)
        with open(Path(workflow.output_dir) / f"{workflow.name}_report.json", "w", encoding="utf-8") as f:
            json.dump(reports, f, indent=2, default=str)
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
