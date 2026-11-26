"""Recompute four-period land-cover and impervious-surface change on the supplied Albers grid."""
import argparse
from contextlib import ExitStack
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from rasterio.windows import Window


YEARS = (2010, 2015, 2020, 2022)
CLASSES = {
    1: "cropland", 2: "forest", 3: "shrub", 4: "grassland", 5: "water",
    6: "snow", 7: "barren", 8: "impervious", 9: "wetland",
}


def analyze(source, output):
    tables = source / "tables"
    catalog = pd.read_csv(Path(__file__).parent / "data/districts.csv")
    lookup = pd.read_csv(tables / "district_lookup.csv").sort_values("raster_id")
    identities = lookup.rename(columns={"adcode": "code", "district_zh": "district", "group_zh": "group"})
    if lookup["raster_id"].tolist() != list(range(1, 22)) or not identities[
        ["code", "district", "group"]
    ].sort_values("code").reset_index(drop=True).equals(catalog.sort_values("code").reset_index(drop=True)):
        raise ValueError("Raster lookup does not match the 21 study districts.")

    counts = np.zeros((len(YEARS), 22, 10), dtype=np.int64)
    transitions = np.zeros((len(YEARS) - 1, 22, 10, 10), dtype=np.int64)
    rasters = source / "rasters"
    with ExitStack() as stack:
        districts = stack.enter_context(rasterio.open(rasters / "CQ_Metro21_district_id.tif"))
        land = [
            stack.enter_context(rasterio.open(rasters / f"CQ_Metro21_LC_{year}.tif"))
            for year in YEARS
        ]
        transform = districts.transform
        if (districts.crs is None or districts.crs.to_dict().get("proj") != "aea"
                or (transform.a, transform.b, transform.d, transform.e) != (30, 0, 0, -30)):
            raise ValueError("Expected a 30 m north-up Albers equal-area grid.")
        for raster in [districts, *land]:
            if (raster.shape, raster.transform, raster.crs, raster.count, raster.dtypes) != (
                districts.shape, transform, districts.crs, 1, ("uint8",)
            ):
                raise ValueError("District and land-cover rasters must share the same integer grid.")

        for top in range(0, districts.height, 256):
            window = Window(0, top, districts.width, min(256, districts.height - top))
            ids = districts.read(1, window=window)
            if np.any(ids > 21):
                raise ValueError("Unexpected district raster code.")
            inside = ids != 0
            district_ids = ids[inside].astype(np.int32)
            prior = None
            for index, raster in enumerate(land):
                current = raster.read(1, window=window)[inside].astype(np.int32)
                if np.any(current > 9):
                    raise ValueError(f"Unexpected land-cover class within study districts in {YEARS[index]}.")
                counts[index] += np.bincount(district_ids * 10 + current, minlength=220).reshape(22, 10)
                if prior is not None:
                    if not np.array_equal(prior == 0, current == 0):
                        raise ValueError("NoData masks differ by year; a common-coverage policy is required.")
                    keys = district_ids * 100 + prior * 10 + current
                    transitions[index - 1] += np.bincount(keys, minlength=2200).reshape(22, 10, 10)
                prior = current

    pixel_area = 30 ** 2 / 1e6
    panel, change = [], []
    for row in identities.itertuples(index=False):
        district_id = row.raster_id
        for index, year in enumerate(YEARS):
            area = counts[index, district_id] * pixel_area
            panel.append({
                "adcode": row.code, "district": row.district, "group": row.group, "year": year,
                "polygon_km2": row.area_km2_albers, "valid_area_km2": area[1:].sum(),
                "nodata_area_km2": area[0],
                **{f"{label}_km2": area[code] for code, label in CLASSES.items()},
            })
            if index:
                matrix = transitions[index - 1, district_id]
                added = int(matrix[1:8, 8].sum() + matrix[9, 8])
                lost = int(matrix[8, 1:8].sum() + matrix[8, 9])
                if added - lost != counts[index, district_id, 8] - counts[index - 1, district_id, 8]:
                    raise ValueError("Pixel transitions do not reconcile with class totals.")
                start = YEARS[index - 1]
                previous_km2 = counts[index - 1, district_id, 8] * pixel_area
                change.append({
                    "adcode": row.code, "district": row.district, "group": row.group,
                    "start": start, "end": year, "added_km2": added * pixel_area,
                    "lost_km2": lost * pixel_area, "net_km2": (added - lost) * pixel_area,
                    "annual_net_km2": (added - lost) * pixel_area / (year - start),
                    "annual_expansion_intensity_pct": (added - lost) * pixel_area * 100
                    / (row.area_km2_albers * (year - start)),
                    "annual_growth_pct": ((area[8] / previous_km2) ** (1 / (year - start)) - 1) * 100
                    if previous_km2 else np.nan,
                })

    panel = pd.DataFrame(panel)
    change = pd.DataFrame(change)
    keys = ["adcode", "year"]
    reference = pd.read_csv(tables / "district_year.csv")
    columns = ["valid_area_km2", "nodata_area_km2", *(f"{x}_km2" for x in CLASSES.values() if x != "snow")]
    reference = reference.set_index(keys).sort_index()
    measured = panel.set_index(keys).sort_index()
    if not measured.index.equals(reference.index):
        raise ValueError("Published and recomputed tables have different district-year keys.")
    max_error = (measured[columns] - reference[columns]).abs().max().max()
    if max_error > 0.000051:
        raise ValueError(f"Recomputed values disagree with the delivered table by {max_error:.6f} km².")
    output.mkdir(parents=True, exist_ok=True)
    panel.to_csv(output / "landcover_recomputed.csv", index=False, float_format="%.6f")
    change.to_csv(output / "impervious_change.csv", index=False, float_format="%.6f")
    panel.groupby(["group", "year"])[columns].sum().to_csv(output / "landcover_groups.csv", float_format="%.6f")
    change.groupby(["group", "start", "end"])[["added_km2", "lost_km2", "net_km2"]].sum().to_csv(
        output / "impervious_change_groups.csv", float_format="%.6f"
    )
    print(f"{len(panel)} district-years; {len(change)} district-period changes; maximum table error {max_error:.8f} km².")
    return panel, change


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="The extracted cq_landcover/out directory")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    analyze(args.source, args.output)
