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


def neighbors(mask):
    return mask[:-2, 1:-1] | mask[2:, 1:-1] | mask[1:-1, :-2] | mask[1:-1, 2:]


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
    morphology = np.zeros((len(YEARS) - 1, 22, 3), dtype=np.int64)
    centroid_sums = np.zeros((len(YEARS), 22, 2))
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
            rows, cols = np.nonzero(inside)
            halo = Window(-1, top - 1, districts.width + 2, window.height + 2)
            prior = None
            for index, raster in enumerate(land):
                cells = raster.read(1, window=halo, boundless=True, fill_value=255)
                current = cells[1:-1, 1:-1][inside].astype(np.int32)
                built = current == 8
                centroid_sums[index, :, 0] += np.bincount(district_ids[built], cols[built], minlength=22)
                centroid_sums[index, :, 1] += np.bincount(district_ids[built], rows[built] + top, minlength=22)
                if np.any(current > 9):
                    raise ValueError(f"Unexpected land-cover class within study districts in {YEARS[index]}.")
                counts[index] += np.bincount(district_ids * 10 + current, minlength=220).reshape(22, 10)
                if prior is not None:
                    if not np.array_equal(prior == 0, current == 0):
                        raise ValueError("NoData masks differ by year; a common-coverage policy is required.")
                    keys = district_ids * 100 + prior * 10 + current
                    transitions[index - 1] += np.bincount(keys, minlength=2200).reshape(22, 10, 10)
                    added = built & (prior != 8) & (prior != 0)
                    adjacent = neighbors(prior_cells == 8)[inside]
                    unknown = neighbors((prior_cells == 0) | (prior_cells == 255))[inside]
                    kinds = np.where(adjacent, 0, np.where(unknown, 2, 1))
                    morphology[index - 1] += np.bincount(
                        district_ids[added] * 3 + kinds[added], minlength=66
                    ).reshape(22, 3)
                prior = current
                prior_cells = cells

    pixel_area = 30 ** 2 / 1e6
    panel, change, flows = [], [], []
    for row in identities.itertuples(index=False):
        district_id = row.raster_id
        previous_centroid = np.array([np.nan, np.nan])
        for index, year in enumerate(YEARS):
            pixels = counts[index, district_id, 8]
            if pixels:
                cell_center = centroid_sums[index, district_id] / pixels + 0.5
                centroid = np.array(transform @ tuple(cell_center))
            else:
                centroid = np.array([np.nan, np.nan])
            area = counts[index, district_id] * pixel_area
            panel.append({
                "adcode": row.code, "district": row.district, "group": row.group, "year": year,
                "polygon_km2": row.area_km2_albers, "valid_area_km2": area[1:].sum(),
                "nodata_area_km2": area[0], "centroid_x_m": centroid[0], "centroid_y_m": centroid[1],
                **{f"{label}_km2": area[code] for code, label in CLASSES.items()},
            })
            if index:
                matrix = transitions[index - 1, district_id]
                valid = matrix[1:, 1:]
                if not (np.array_equal(valid.sum(axis=1), counts[index-1, district_id, 1:])
                        and np.array_equal(valid.sum(axis=0), counts[index, district_id, 1:])):
                    raise ValueError("Transition matrix margins do not match annual class counts.")
                for origin in CLASSES:
                    for destination in CLASSES:
                        pixels_changed = int(matrix[origin, destination])
                        flows.append((row.code, row.district, row.group, YEARS[index-1], year,
                                      origin, destination, pixels_changed, pixels_changed * pixel_area))
                added = int(matrix[1:8, 8].sum() + matrix[9, 8])
                lost = int(matrix[8, 1:8].sum() + matrix[8, 9])
                if added - lost != counts[index, district_id, 8] - counts[index - 1, district_id, 8]:
                    raise ValueError("Pixel transitions do not reconcile with class totals.")
                adjacent, detached, unknown = morphology[index - 1, district_id]
                if adjacent + detached + unknown != added:
                    raise ValueError("Morphology pixel counts do not reconcile with additions.")
                dx, dy = centroid - previous_centroid
                displacement = np.hypot(dx, dy)
                start = YEARS[index - 1]
                previous_km2 = counts[index - 1, district_id, 8] * pixel_area
                change.append({
                    "adcode": row.code, "district": row.district, "group": row.group,
                    "start": start, "end": year, "added_km2": added * pixel_area,
                    "lost_km2": lost * pixel_area, "net_km2": (added - lost) * pixel_area,
                    "adjacent_km2": adjacent * pixel_area, "nonadjacent_km2": detached * pixel_area,
                    "adjacency_unknown_km2": unknown * pixel_area,
                    "centroid_displacement_km": displacement / 1000,
                    "centroid_bearing_deg": np.degrees(np.arctan2(dx, dy)) % 360 if displacement > 0 else np.nan,
                    "annual_net_km2": (added - lost) * pixel_area / (year - start),
                    "annual_expansion_intensity_pct": (added - lost) * pixel_area * 100
                    / (row.area_km2_albers * (year - start)),
                    "annual_growth_pct": ((area[8] / previous_km2) ** (1 / (year - start)) - 1) * 100
                    if previous_km2 else np.nan,
                })
            previous_centroid = centroid

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
    pd.DataFrame(flows, columns=["adcode","district","group","start","end","from_class",
                                 "to_class","pixel_count","area_km2"]).to_csv(
        output / "class_transitions.csv", index=False, float_format="%.6f"
    )
    panel.to_csv(output / "landcover_recomputed.csv", index=False, float_format="%.6f")
    change.to_csv(output / "impervious_change.csv", index=False, float_format="%.6f")
    panel.groupby(["group", "year"])[columns].sum().to_csv(output / "landcover_groups.csv", float_format="%.6f")
    change.groupby(["group", "start", "end"])[[
        "added_km2", "lost_km2", "net_km2", "adjacent_km2", "nonadjacent_km2", "adjacency_unknown_km2"
    ]].sum().to_csv(
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
