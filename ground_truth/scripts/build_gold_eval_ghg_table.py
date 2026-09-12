"""
Build ready-made GHG gold-answer tables from GHG.xlsx's "Deduplicated"
sheet, reshaped and renamed onto this repo's schema/cover_crop_schema.yml
field names -- so the future eval harness can diff pipeline output
against these columns directly, without waiting for the pipeline to
(re-)extract anything the spreadsheet already has confirmed (per Yu
Peng, 2026-09-11).

Two structural gaps this script has to bridge, both real, not
oversights:

1. Row granularity. Our schema is long-format: one row = one design
   combination x ONE response variable (one gas at a time, via
   `gas_type`). GHG.xlsx Deduplicated is wide: co2_cc/n2o_cc/ch4_cc
   side by side in one row. This script MELTS each Deduplicated row
   into up to 3 output rows (one per gas actually reported), carrying
   the same `source_ghg_row_id` so they can be traced back to one
   original row.

2. Column coverage. Only some Deduplicated columns have a same-meaning
   field in the current schema (see DIRECT_MAP below) -- those are
   renamed onto schema field names. Everything else with no schema home
   yet (cropping_system_category/classification, CC.duration, CC.days,
   replications, Plot_Area_ha, mixture_types/propotion,
   residue_management, SOC_initial, ...) is kept, unrenamed, under an
   `extra__` prefix so nothing is silently dropped -- these are exactly
   the fields flagged in cc-groundtruth-workflow-v0.md as "not yet
   reconciled against the pipeline's schema."

CONFIRMED by Yu Peng (2026-09-12): `CC.duration` in the source IS the
same concept as this project's `cc_duration_years` field ("the total
number of years cover crop was used"), so it is renamed onto that
schema field name below rather than kept under an `extra__` prefix.
"""
import os
from pathlib import Path

import pandas as pd

_DEFAULT_DIR = "/Users/yupe4788/Library/CloudStorage/OneDrive-UCB-O365/1.Research 4.49.41 PM/1. Main Project/7. CC maps"
GHG_XLSX = os.environ.get("GHG_XLSX_PATH", f"{_DEFAULT_DIR}/GHG.xlsx")
OUT_DIR = Path(__file__).resolve().parents[1] / "output"

# Deduplicated column -> schema field name (only columns with a real,
# same-meaning schema field; see module docstring for the rest).
DIRECT_MAP = {
    "paper_id": "paper_id",
    "paper_doi": "doi",
    "latitude": "latitude",
    "longitude": "longitude",
    "year": "year",
    "country": "country",
    "CC_species": "cc_species",
    "CC_types": "cc_category",       # legume/non-legume/mixture/rotation
    "tillage": "tillage_type_raw",
    "cash_crop_specices": "grain_crop_raw",
    "CC_plant_date": "cc_planting_time_raw",
    "CC_end_date": "cc_terminating_time_raw",
    "irrigation": "irrigation_raw",
    "N_fertilization": "fertilize_raw",
    "CC.duration": "cc_duration_years",
}

GAS_COLUMNS = {
    "co2": dict(cc="co2_cc", no_cc="co2_no_cc", cc_sd="co2_cc_sd", no_cc_sd="co2_no_cc_sd",
                unit="co2_unit", n="co2_n"),
    "n2o": dict(cc="n2o_cc", no_cc="n2o_no_cc", cc_sd="n2o_cc_sd", no_cc_sd="n2o_no_cc_sd",
                unit="n2o_unit", n=None),
    "ch4": dict(cc="ch4_cc", no_cc="ch4_no_cc", cc_sd="ch4_cc_sd", no_cc_sd="ch4_no_cc_sd",
                unit="ch4_unit", n=None),
}


def build_location(row) -> str:
    parts = [row.get("specific_location"), row.get("region_state")]
    parts = [str(p).strip() for p in parts if pd.notna(p) and str(p).strip()]
    return "; ".join(parts) if parts else None


def melt_gas_rows(dd: pd.DataFrame) -> pd.DataFrame:
    out_rows = []
    for _, row in dd.iterrows():
        base = {"source_ghg_row_id": row["id"]}
        for schema_col, src_col in DIRECT_MAP.items():
            base[src_col] = row.get(schema_col)
        base["location"] = build_location(row)
        # soil_texture_raw: prefer the fuller `soil_texture` column,
        # fall back to the sparser `soilTexture`
        base["soil_texture_raw"] = row.get("soil_texture")
        if pd.isna(base["soil_texture_raw"]):
            base["soil_texture_raw"] = row.get("soilTexture")
        # everything else, unrenamed, so nothing is silently dropped
        for col in dd.columns:
            if col in DIRECT_MAP or col in ("id", "specific_location", "region_state",
                                             "soil_texture", "soilTexture"):
                continue
            if col.split("_")[0] in GAS_COLUMNS or col in (
                "co2_unit", "n2o_unit", "ch4_unit", "co2_n"
            ):
                continue
            base[f"extra__{col}"] = row.get(col)

        any_gas = False
        for gas, cols in GAS_COLUMNS.items():
            cc_val = row.get(cols["cc"])
            if pd.isna(cc_val):
                continue
            any_gas = True
            r = dict(base)
            r["gas_type"] = gas
            r["ghg_cc_mean"] = cc_val
            r["ghg_control_mean"] = row.get(cols["no_cc"])
            r["ghg_cc_sd"] = row.get(cols["cc_sd"])
            r["ghg_control_sd"] = row.get(cols["no_cc_sd"])
            r["ghg_unit"] = row.get(cols["unit"])
            r["ghg_n"] = row.get(cols["n"]) if cols["n"] else None
            out_rows.append(r)
        if not any_gas:
            # keep the row even with no GHG value reported, for traceability
            r = dict(base)
            r["gas_type"] = None
            out_rows.append(r)
    return pd.DataFrame(out_rows)


def main() -> None:
    dd = pd.read_excel(GHG_XLSX, sheet_name="Deduplicated")
    tier1 = dd[dd["manul checked & revised"] == "y"]
    tier2 = dd[dd["manul checked & revised"] != "y"]

    for name, subset in [("tier1", tier1), ("tier2", tier2)]:
        melted = melt_gas_rows(subset)
        out_path = OUT_DIR / f"gold_eval_ghg_{name}.csv"
        melted.to_csv(out_path, index=False)
        print(f"{name}: {len(subset)} source rows -> {len(melted)} gold eval rows "
              f"({melted['gas_type'].notna().sum()} carry a GHG value) -> {out_path}")


if __name__ == "__main__":
    main()
