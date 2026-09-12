"""
Apply the three confirmed decisions (2026-09-11 conversation with Yu Peng)
on top of species_normalization_table.csv:

  1. Merge confirmed typo/formatting-only duplicate species-combination
     entries (never auto-merges anything that differs in species
     identity or mixture proportions -- those stay separate, and two
     genuinely ambiguous cases are left as OPEN_REVIEW for Yu Peng).
  2. Resolve the one real data conflict: "Cereal Rye" -> Non-legume
     (confirmed). The YieldTable.xlsx rows that say "Legume" for Cereal
     Rye are a systematic mislabel (24 of 25 rows, spanning many
     different papers/batches) -- flagged in
     yieldtable_data_issues_for_review.csv rather than silently
     corrected in the user's source spreadsheet.
  3. Fill tier-3 family. GBIF/WFO lookup is NOT reachable from this
     network (both the local device shell and the cloud sandbox reject
     api.gbif.org / worldfloraonline.org under the org's egress policy)
     -- so family is filled from ordinary botanical classification
     instead, using two safe rules plus a per-genus dictionary, and
     NEEDS_CONFIRMATION is kept wherever neither applies:
       a. functional_group == "Legume" (single value, no conflict) =>
          Fabaceae. This is close to definitional (the legume/
          non-legume tag in this dataset IS a Fabaceae/not-Fabaceae
          split), so it is treated as high-confidence, not a guess.
       b. functional_group in {"Mixture"} or a "..._RT" rotation entry
          => "Mixture (multiple families)" / "Rotation (multiple
          families/phases)" -- a mixture's own components may span
          several families, so a single family label would misrepresent
          it. One exception: Sorghum x Sudangrass is a single-family
          intra-Poaceae hybrid, not a multi-species mixture, so it gets
          Poaceae directly.
       c. Everything else (mostly single non-legume species) is looked
          up in COMMON_NAME_FAMILY below, built from standard
          agronomic/botanical references. A name not in the dictionary
          stays NEEDS_CONFIRMATION -- never guessed.

     One source-data correction is also applied: YieldTable.xlsx's
     Unnamed: 12 column tags "Phacelia" as Brassicaceae, which is
     wrong (Phacelia is Boraginaceae) -- overridden here and flagged in
     yieldtable_data_issues_for_review.csv.
"""
from pathlib import Path

import pandas as pd

OUT_DIR = Path(__file__).resolve().parents[1] / "output"
IN_CSV = OUT_DIR / "species_normalization_table.csv"

# --- 1. confirmed merge groups (typo / formatting variants only) ---
# each group: (canonical spelling, [all raw variants that mean the same thing])
MERGE_GROUPS = [
    ("Cereal Rye + Hairy Vetch", ["Ceral Rye + Hariy Vetch", "Ceral Rye + Hairy Vetch",
                                   "cereal rye & hairy vetch", "Cereal Rye/Hairy Vetch"]),
    ("Sunn Hemp", ["Sunnhemp", "Sunn Hemp"]),
    ("Rye + Hairy Vetch", ["Rye+Hairy Vetch", "Rye + Hairy Vetch"]),
    ("Cereal Rye + Crimson Clover", ["Cereal Rye/Crimon Clover", "cereal rye & crimson clover"]),
    ("Oilseed Radish + Rye", ["Oilseed radish & Rye", "Oilseed radish+Rye"]),
    ("Pea + Canola", ["Pea & Canola", "pea and canola"]),
]

# --- open questions Yu Peng has NOT yet resolved -- left untouched ---
OPEN_REVIEW_NOTE = (
    "Whether 'Rye'/'Cereal Rye'/'Winter Rye' (and their mixture combos, e.g. "
    "'Rye + Hairy Vetch' vs 'Cereal Rye + Hairy Vetch' vs 'winter rye & hairy "
    "vetch') refer to the same species tracked under different labels, or are "
    "deliberately distinct categories -- the existing table already keeps "
    "'Rye' (143 rows) and 'Cereal Rye' (28 rows) as separate top-level "
    "entries elsewhere, so this script does NOT merge these on its own."
)

# --- 2. Cereal Rye functional-group fix ---
CEREAL_RYE_FIX = {"tier2_common_name": "Cereal Rye", "correct_functional_group": "Non-legume"}

# --- 3. family dictionary for single (non-legume) species/genera ---
COMMON_NAME_FAMILY = {
    "rye": "Poaceae", "oat": "Poaceae", "black oat": "Poaceae", "spring oat": "Poaceae",
    "oilseed radish": "Brassicaceae", "ryegrass": "Poaceae", "cereal rye": "Poaceae",
    "triticale": "Poaceae", "winter triticale": "Poaceae", "spring triticale": "Poaceae",
    "wheat": "Poaceae", "winter wheat": "Poaceae", "spring wheat": "Poaceae",
    "winter rye": "Poaceae", "annual ryegrass": "Poaceae", "italian ryegrass": "Poaceae",
    "camelina": "Brassicaceae", "winter camelina": "Brassicaceae", "barley": "Poaceae",
    "spring barley": "Poaceae", "winter barley": "Poaceae", "millet": "Poaceae",
    "pearl millet": "Poaceae", "sudan grass": "Poaceae", "forage sorghum": "Poaceae",
    "mustard": "Brassicaceae", "white mustard": "Brassicaceae", "winter rape": "Brassicaceae",
    "rapeseed": "Brassicaceae", "pennycress": "Brassicaceae", "winter turnip": "Brassicaceae",
    "brassica rapa": "Brassicaceae", "buckwheat": "Polygonaceae",
    "agrostemma (corn cockle)": "Caryophyllaceae", "guizotia abyssinica": "Asteraceae",
    "phacelia": "Boraginaceae",  # correction -- see module docstring
    "quinoa": "Amaranthaceae", "garlic": "Amaryllidaceae", "sunflower": "Asteraceae",
    "guinea grass": "Poaceae", "palisade grass": "Poaceae", "congo grass": "Poaceae",
    "signalgrass": "Poaceae", "reed canary grass": "Poaceae", "brachiaria": "Poaceae",
    "c.bluegrass": "Poaceae", "cereal rye (158 kg ha−1)": "Poaceae",
    "sorghum × sudan grass": "Poaceae",  # single-family hybrid, not a multi-species mix
    "fodder raddish": "Brassicaceae",  # = fodder radish, same species as Oilseed Radish
}

FABACEAE_GENUS_HINTS = {
    # sanity list of the Legume-tagged entries, for the printed report only
    "hairy vetch", "vetch", "pea", "sunnhemp", "sunn hemp", "subterranean clover",
    "mung bean", "crimson clover", "soybean", "red clover", "alfalfa", "clover",
    "common vetch", "crotalaria spectabilis", "blue lupin", "grass pea", "kidney vetch",
    "milk vetch", "velvet bean", "white hoary pea", "fish poison bean", "devil bean",
    "sweet clover", "forage pea", "green gram", "chinese milk vetch", "mucuna pruriens",
    "dwarf pigeonpea", "showy rattlebox", "jack bean", "faba bean", "galega",
    "huai bean", "austrian  pea", "white clover",
}


def main() -> None:
    df = pd.read_csv(IN_CSV, keep_default_na=False)

    # ---- 1. apply merges ----
    merge_log = []
    key_to_canonical = {}
    for canonical, variants in MERGE_GROUPS:
        for v in variants:
            key_to_canonical[v] = canonical

    def collapse(group_df, canonical):
        raw_variants = set()
        for rv in group_df["raw_variants_seen"]:
            raw_variants.update(x.strip() for x in str(rv).split(";") if x.strip())
        merged = {
            "tier2_common_name": canonical,
            "tier3_family": "Mixture (multiple families)",
            "tier4_functional_group": "Mixture",
            "functional_group_raw_needs_review": "",
            "cc_type_values_seen": "; ".join(sorted(set(
                x for v in group_df["cc_type_values_seen"] for x in str(v).split("; ") if x
            ))),
            "yield_table_count": group_df["yield_table_count"].sum(),
            "ghg_table_count": group_df["ghg_table_count"].sum(),
            "raw_variants_seen": "; ".join(sorted(raw_variants)),
        }
        merge_log.append({
            "canonical": canonical,
            "merged_from": "; ".join(sorted(group_df["tier2_common_name"].tolist())),
            "rows_merged": len(group_df),
        })
        return merged

    rows = []
    handled = set()
    for canonical, variants in MERGE_GROUPS:
        group_df = df[df["tier2_common_name"].isin(variants)]
        if len(group_df) == 0:
            continue
        rows.append(collapse(group_df, canonical))
        handled.update(group_df.index.tolist())

    remaining = df[~df.index.isin(handled)].copy()
    merged_df = pd.concat([remaining, pd.DataFrame(rows)], ignore_index=True)

    # ---- 2. Cereal Rye functional-group fix ----
    mask = merged_df["tier2_common_name"] == CEREAL_RYE_FIX["tier2_common_name"]
    merged_df.loc[mask, "tier4_functional_group"] = CEREAL_RYE_FIX["correct_functional_group"]

    # ---- 3. family fill ----
    def fill_family(row):
        name = str(row["tier2_common_name"])
        key = name.strip().lower()
        fg = str(row["tier4_functional_group"])
        if key in COMMON_NAME_FAMILY:
            return COMMON_NAME_FAMILY[key], "botanical_knowledge"
        if fg == "Legume":
            return "Fabaceae", "legume_rule (functional_group=Legume)"
        if fg == "Mixture":
            return "Mixture (multiple families)", "mixture_multiple_families"
        if fg == "Rotation":
            return "Rotation (multiple families/phases)", "rotation_multiple_phases"
        if row["tier3_family"] not in ("NEEDS_CONFIRMATION", ""):
            return row["tier3_family"], "already_in_source_table"
        return "NEEDS_CONFIRMATION", "no_rule_matched"

    # Tier-3 family fill is DISABLED per Yu Peng's 2026-09-11 call ("not for
    # now") -- GBIF/WFO is unreachable from this network so the fill would
    # have relied on a hardcoded botanical dictionary + the legume-rule
    # heuristic below rather than a real lookup; left in place (unused) in
    # case a real GBIF/WFO path becomes available later. Family stays
    # whatever the source tables already say (mostly NEEDS_CONFIRMATION).
    FILL_TIER3_FAMILY = False
    if FILL_TIER3_FAMILY:
        filled = merged_df.apply(lambda r: fill_family(r), axis=1, result_type="expand")
        merged_df["tier3_family"] = filled[0]
        merged_df["tier3_family_method"] = filled[1]
    else:
        merged_df["tier3_family_method"] = "not_attempted"

    merged_df = merged_df.sort_values(
        by=["yield_table_count", "ghg_table_count"], ascending=False
    ).reset_index(drop=True)
    merged_df.to_csv(IN_CSV, index=False)

    pd.DataFrame(merge_log).to_csv(OUT_DIR / "species_merge_log.csv", index=False)

    with open(OUT_DIR / "species_open_review_notes.txt", "w") as f:
        f.write(OPEN_REVIEW_NOTE + "\n")

    print(f"Final canonical entries: {len(merged_df)} (was {len(df)}, merged {sum(l['rows_merged'] for l in merge_log)} rows into {len(merge_log)} groups)")
    print(merged_df["tier3_family_method"].value_counts())
    print(f"Still NEEDS_CONFIRMATION: {(merged_df['tier3_family']=='NEEDS_CONFIRMATION').sum()}")


if __name__ == "__main__":
    main()
