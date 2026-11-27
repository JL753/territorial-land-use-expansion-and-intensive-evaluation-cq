"""Join the supplied yearbook panel with the verified native-grid land-cover results."""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from shapely import make_valid
from shapely.geometry import mapping, shape
from shapely.ops import unary_union

from evaluate import evaluate, load_panel, write_outputs

KEYS = ["code", "year"]
ECONOMY = {
    "population_person": "population",
    "gdp_10k_yuan": "gdp_10k_cny",
    "secondary_10k_yuan": "secondary_10k_cny",
}
ALTERNATE = {
    "500110": (2165533, 1033502),
    "500111": (1850329, 1045814),
}


def load_observed(socio, landcover, output):
    stats = pd.read_csv(socio, dtype={"adcode": "string"}).rename(columns={"adcode": "code", **ECONOMY})
    land = pd.read_csv(landcover / "landcover_recomputed.csv", dtype={"adcode": "string"}).rename(
        columns={"adcode": "code", "impervious_km2": "built_km2", "polygon_km2": "admin_km2"}
    )
    district_keys = [*KEYS, "district", "group"]
    merged = land.merge(stats, on=district_keys, how="outer", validate="one_to_one", indicator=True)
    if len(merged) != 84 or not merged["_merge"].eq("both").all():
        raise ValueError("Expected 84 matching district-year observations.")
    if (merged["secondary_10k_cny"] > merged["gdp_10k_cny"]).any():
        raise ValueError("Second-sector value added exceeds GDP.")
    sectors = merged[["primary_10k_yuan", "secondary_10k_cny", "tertiary_10k_yuan"]]
    if (sectors < 0).any().any() or not np.allclose(
        sectors.sum(axis=1, skipna=False), merged["gdp_10k_cny"], atol=1.01, rtol=0
    ):
        raise ValueError("Industry components do not reconcile with GDP.")
    changes = pd.read_csv(landcover / "impervious_change.csv", dtype={"adcode": "string"}).rename(
        columns={"adcode": "code", "end": "year"}
    )
    change_columns = [
        "added_km2", "lost_km2", "adjacent_km2", "nonadjacent_km2", "adjacency_unknown_km2",
        "centroid_displacement_km", "centroid_bearing_deg",
    ]
    merged = merged.merge(changes[[*KEYS, *change_columns]], on=KEYS, how="left", validate="one_to_one")
    merged["provisional"] = merged[["quality_population", "quality_gdp", "quality_secondary"]].ne("A").any(axis=1)
    panel_path = output / "panel.csv"
    merged.drop(columns="_merge").to_csv(panel_path, index=False)
    return load_panel(panel_path)


def map_boundaries(path, panel):
    collection = json.loads(path.read_text(encoding="utf-8"))
    catalog = panel.set_index("code")[["district", "group"]].to_dict("index")
    geometries = []
    for feature in collection["features"]:
        code = str(feature["properties"]["adcode"])
        if feature["properties"].get("delivered_crs") != "WGS84" or code not in catalog:
            raise ValueError(f"Expected a supplied WGS84 district boundary: {code}")
        geometry = make_valid(shape(feature["geometry"]))
        if geometry.geom_type == "GeometryCollection":
            geometry = unary_union([part for part in geometry.geoms if part.geom_type in {"Polygon", "MultiPolygon"}])
        if geometry.geom_type not in {"Polygon", "MultiPolygon"} or not geometry.is_valid or geometry.is_empty:
            raise ValueError(f"Could not obtain a valid district polygon for {code}.")
        geometries.append({
            "type": "Feature", "properties": {"code": code, **catalog[code]}, "geometry": mapping(geometry),
        })
    if len(geometries) != 21 or {f["properties"]["code"] for f in geometries} != set(catalog):
        raise ValueError("Expected exactly 21 district features.")
    return {"type": "FeatureCollection", "features": geometries}


def run(args):
    args.output.mkdir(parents=True, exist_ok=True)
    panel = load_observed(args.socio, args.landcover, args.output)
    full, weights = evaluate(panel)
    recent_panel = panel[panel["year"].isin([2020, 2022])].copy()
    if recent_panel["provisional"].any() or len(recent_panel) != 42:
        raise ValueError("Expected 42 recent observations with all three source grades marked A.")
    recent, recent_weights = evaluate(recent_panel)
    alternate = panel.copy()
    for code, values in ALTERNATE.items():
        alternate.loc[(alternate["code"] == code) & (alternate["year"] == 2010),
                      ["gdp_10k_cny", "secondary_10k_cny"]] = values
    alternate, _ = evaluate(alternate)
    comparison = full[[*KEYS, "district", "rank", "intensive_score"]].merge(
        alternate[[*KEYS, "rank", "intensive_score"]], on=KEYS, suffixes=("_bundle", "_merged")
    )
    comparison.to_csv(args.output / "historical_basis_sensitivity.csv", index=False)
    write_outputs(full, weights, args.output / "four-year-exploratory", "observed")
    write_outputs(recent, recent_weights, args.output / "recent-year-comparison", "observed")
    districts = full.drop_duplicates("code")
    geometry = map_boundaries(args.boundaries, districts)
    # All four years share the exploratory normalization and ideal points.
    dashboard = args.output / "four-year-exploratory"
    full["evaluation_basis"] = "nominal_four_year_exploratory"
    transition_file = args.landcover / "class_transitions.csv"
    if transition_file.exists():
        transitions = pd.read_csv(transition_file, dtype={"adcode": str})
        matrices = {}
        for key, cells in transitions.groupby(["adcode", "end"]):
            matrix = cells.pivot(index="from_class", columns="to_class", values="area_km2")
            if list(matrix.index) != list(range(1, 10)) or list(matrix.columns) != list(range(1, 10)) or matrix.isna().any().any():
                raise ValueError(f"Incomplete transition matrix for {key}")
            matrices[key] = matrix.to_numpy().tolist()
        full["transition_km2"] = [None if pd.isna(row.interval_start) else matrices[(row.code, row.year)]
                                  for row in full.itertuples()]
    (dashboard / "dashboard.json").write_text(full.to_json(orient="records", force_ascii=False), encoding="utf-8")
    (dashboard / "districts.geojson").write_text(json.dumps(geometry, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ["socio", "landcover", "boundaries", "output"]:
        parser.add_argument(f"--{flag}", required=True, type=Path)
    run(parser.parse_args())
