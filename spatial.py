"""Extract construction land and expansion morphology, then join district statistics."""
import argparse
from contextlib import ExitStack
import json
from math import ceil, floor
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from rasterio.features import geometry_mask
from rasterio.transform import from_origin
from rasterio.vrt import WarpedVRT
from rasterio.warp import transform_geom
from rasterio.windows import Window, from_bounds
from shapely.geometry import shape, mapping

from evaluate import evaluate, load_panel, write_outputs

YEARS = (2010, 2015, 2020, 2022)
CRS = "EPSG:6933"
CELL = 30
AREA = CELL ** 2 / 1e6
TILE = 512


def read_boundaries(path, codes):
    collection = json.loads(path.read_text(encoding="utf-8"))
    if collection.get("type") != "FeatureCollection" or "crs" in collection:
        raise ValueError("Use an RFC 7946 WGS84 GeoJSON FeatureCollection.")
    geometries = {}
    for feature in collection["features"]:
        code = str(feature["properties"]["code"])
        geometry = shape(feature["geometry"])
        if code in geometries or geometry.geom_type not in {"Polygon", "MultiPolygon"}:
            raise ValueError(f"Expected one polygon or multipolygon per code: {code}")
        if geometry.is_empty or not geometry.is_valid:
            raise ValueError(f"Invalid geometry: {code}")
        west, south, east, north = geometry.bounds
        if not (-180 <= west <= east <= 180 and -90 <= south <= north <= 90):
            raise ValueError(f"Expected WGS84 coordinates: {code}")
        projected = transform_geom("EPSG:4326", CRS, mapping(geometry))
        geometries[code] = shape(projected)
    if set(geometries) != set(codes):
        raise ValueError("Boundary codes must match the study district catalog.")
    for i, (code, geometry) in enumerate(geometries.items()):
        for other, neighbor in list(geometries.items())[i+1:]:
            if geometry.intersection(neighbor).area > 1:
                raise ValueError(f"Overlapping districts: {code}, {other}")
    return collection, geometries


def has_neighbor(mask):
    return mask[:-2, 1:-1] | mask[2:, 1:-1] | mask[1:-1, :-2] | mask[1:-1, 2:]


def district_counts(vrts, grid, geometry, built_class):
    bounds = from_bounds(*geometry.bounds, transform=grid)
    left, top = floor(bounds.col_off), floor(bounds.row_off)
    right = ceil(bounds.col_off + bounds.width)
    bottom = ceil(bounds.row_off + bounds.height)
    counts = {year: np.zeros(7, dtype=np.int64) for year in vrts}
    for y in range(top, bottom, TILE):
        for x in range(left, right, TILE):
            h, w = min(TILE, bottom-y), min(TILE, right-x)
            window = Window(x, y, w, h)
            inside = geometry_mask([mapping(geometry)], (h, w),
                                   rasterio.windows.transform(window, grid), invert=True)
            if not inside.any():
                continue
            halo = Window(x-1, y-1, w+2, h+2)
            previous = None
            for year, vrt in vrts.items():
                raster = vrt.read(1, window=halo, masked=True)
                if (np.ma.getmaskarray(raster)[1:-1, 1:-1] & inside).any():
                    raise ValueError(f"Raster coverage gap in {year}.")
                built = (raster == built_class).filled(False)
                center = built[1:-1, 1:-1]
                rows, cols = np.nonzero(center & inside)
                counts[year][0] += len(rows)
                counts[year][5:] += [np.sum(cols + x), np.sum(rows + y)]
                if previous is not None:
                    old = previous[1:-1, 1:-1]
                    adjacent = has_neighbor(previous)
                    added = center & ~old & inside
                    if (added & ~adjacent & has_neighbor(previous_mask)).any():
                        raise ValueError(f"Coverage gap near new land in {year}; supply a raster buffer.")
                    counts[year][1:5] += [
                        np.count_nonzero(added), np.count_nonzero(old & ~center & inside),
                        np.count_nonzero(added & adjacent), np.count_nonzero(added & ~adjacent),
                    ]
                previous = built
                previous_mask = np.ma.getmaskarray(raster)
    return counts


def run(boundaries, stats_path, catalog_path, rasters, built_class, output, kind):
    catalog = pd.read_csv(catalog_path, dtype={"code": str}).set_index("code", verify_integrity=True)
    if tuple(sorted(rasters)) != YEARS:
        raise ValueError(f"Supply the four raster years {YEARS}.")
    collection, geometries = read_boundaries(boundaries, catalog.index)
    stats = pd.read_csv(stats_path, dtype={"code": str})
    required = {"code", "year", "population", "gdp_10k_cny", "secondary_10k_cny",
                "source", "price_basis", "boundary_basis"}
    if not required <= set(stats):
        raise ValueError(f"Missing statistics fields: {sorted(required - set(stats))}")
    expected = {(code, year) for code in catalog.index for year in YEARS}
    if len(stats) != len(expected) or set(zip(stats["code"], stats["year"])) != expected:
        raise ValueError("Statistics must cover every district × study year exactly once.")
    for column in ["source", "price_basis", "boundary_basis"]:
        if stats[column].isna().any() or stats[column].str.strip().eq("").any():
            raise ValueError(f"Missing provenance: {column}")
    for column in ["price_basis", "boundary_basis"]:
        if stats[column].nunique() != 1:
            raise ValueError(f"Use a consistent {column} across the panel.")

    west = min(g.bounds[0] for g in geometries.values())
    south = min(g.bounds[1] for g in geometries.values())
    east = max(g.bounds[2] for g in geometries.values())
    north = max(g.bounds[3] for g in geometries.values())
    x0 = (floor(west / CELL) - 1) * CELL
    y0 = (ceil(north / CELL) + 1) * CELL
    grid = from_origin(x0, y0, CELL, CELL)
    width = ceil((east - x0) / CELL) + 1
    height = ceil((y0 - south) / CELL) + 1
    spatial = []
    with ExitStack() as stack:
        vrts = {}
        for year, path in sorted(rasters.items()):
            source = stack.enter_context(rasterio.open(path))
            if source.crs is None or source.count != 1 or not np.issubdtype(np.dtype(source.dtypes[0]), np.integer):
                raise ValueError(f"{year}: expected a georeferenced single-band categorical raster.")
            if source.nodata == built_class:
                raise ValueError(f"{year}: construction class conflicts with NoData.")
            vrts[year] = stack.enter_context(WarpedVRT(
                source, crs=CRS, transform=grid, width=width, height=height,
                dtype="int32", nodata=-9999, resampling=rasterio.enums.Resampling.nearest,
            ))
        for code, geometry in geometries.items():
            counts = district_counts(vrts, grid, geometry, built_class)
            for year, (built, added, lost, adjacent, detached, col_sum, row_sum) in counts.items():
                change = (added, lost, adjacent, detached)
                metrics = [int(value) * AREA for value in change] if year != YEARS[0] else [None] * 4
                if built == 0:
                    raise ValueError(f"{code} {year}: no construction land. Check coverage and class code.")
                cx, cy = grid @ (col_sum / built + 0.5, row_sum / built + 0.5)
                spatial.append([code, year, geometry.area / 1e6, int(built) * AREA, *metrics, cx, cy])
    columns = ["code", "year", "admin_km2", "built_km2", "added_km2", "lost_km2",
               "adjacent_km2", "nonadjacent_km2", "centroid_x_m", "centroid_y_m"]
    panel = pd.DataFrame(spatial, columns=columns).merge(stats, on=["code", "year"], validate="one_to_one")
    panel = panel.join(catalog[["district", "group"]], on="code")
    output.mkdir(parents=True, exist_ok=True)
    panel_file = output / "panel.csv"
    panel.to_csv(panel_file, index=False)
    results, weights = evaluate(load_panel(panel_file))
    centroids = results.groupby("code")[["centroid_x_m", "centroid_y_m"]].diff()
    dx, dy = centroids["centroid_x_m"], centroids["centroid_y_m"]
    results["centroid_displacement_km"] = np.hypot(dx, dy) / 1000
    results["centroid_bearing_deg"] = ((np.degrees(np.arctan2(dx, dy)) + 360) % 360).where(
        results["centroid_displacement_km"] > 1e-10
    )
    intervals = results.dropna(subset=["interval_start"])
    if not np.allclose(intervals["added_km2"] - intervals["lost_km2"], intervals["expansion_km2"]):
        raise ValueError("Change totals do not reconcile.")
    write_outputs(results, weights, output, kind)
    for feature in collection["features"]:
        code = str(feature["properties"]["code"])
        feature["properties"] = {"code": code, **catalog.loc[code].to_dict()}
    (output / "districts.geojson").write_text(json.dumps(collection, ensure_ascii=False), encoding="utf-8")
    (output / "dashboard.json").write_text(results.to_json(orient="records", force_ascii=False), encoding="utf-8")
    summaries = results.groupby(["group", "year"], as_index=False).agg(
        districts=("code", "size"), built_km2=("built_km2", "sum"),
        mean_score=("intensive_score", "mean"),
    )
    summaries.assign(data_kind=kind).to_csv(output / "groups.csv", index=False)
    write_report(output, kind, results, summaries, weights)


def write_report(output, kind, results, summaries, weights):
    title = "模拟流程验证" if kind == "demo" else "实测数据描述统计"
    totals = results.groupby("year")["built_km2"].sum()
    lines = [
        f"# 重庆市主城都市区建设用地分析 · {title}", "",
        f"数据类型为 `{kind}`。观测共 {len(results)} 条。", "",
        "## 土地覆盖与分组统计", "",
        "| 年份 | 研究区建设用地面积（km²） | 中心城区得分均值 | 主城新区得分均值 |",
        "|---|---:|---:|---:|",
    ]
    for year, area in totals.items():
        groups = summaries[summaries["year"] == year].set_index("group")["mean_score"]
        lines.append(f"| {year} | {area:.4f} | {groups.get('中心城区', np.nan):.4f} | {groups.get('主城新区', np.nan):.4f} |")
    lines += ["", "## 熵权与敏感性", "",
              "| 指标 | 熵权 |", "|---|---:|"]
    for indicator, weight in weights.items():
        lines.append(f"| {indicator} | {weight:.4f} |")
    moved = int((results["rank"] != results["equal_weight_rank"]).sum())
    lines += ["", f"使用等权 TOPSIS 后，有 {moved} 条观测的同年名次发生变化。", "",
              "阶段扩张与期末得分的区际 Spearman 系数见 association.csv。", "",
              "结果仅反映输入数据和定义下的描述统计。", ""]
    (output / "report.md").write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--boundaries", type=Path, required=True)
    parser.add_argument("--statistics", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, default=Path("data/districts.csv"))
    parser.add_argument("--raster", action="append", nargs=2, metavar=("YEAR", "PATH"), required=True)
    parser.add_argument("--built-class", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--data-kind", choices=["demo", "observed"], required=True)
    args = parser.parse_args()
    try:
        rasters = {int(year): Path(path) for year, path in args.raster}
        if len(rasters) != len(args.raster):
            raise ValueError("Duplicate raster year.")
        run(args.boundaries, args.statistics, args.catalog, rasters,
            args.built_class, args.output, args.data_kind)
    except (ValueError, OSError, KeyError, TypeError) as error:
        parser.exit(1, f"Spatial analysis failed: {error}\n")


if __name__ == "__main__":
    main()
