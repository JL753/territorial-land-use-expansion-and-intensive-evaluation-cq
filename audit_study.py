"""Audit internal consistency and provenance metadata of the published study data."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from shapely.geometry import shape

YEARS = (2010, 2015, 2020, 2022)
INTERVALS = ((2010, 2015), (2015, 2020), (2020, 2022))
PIXEL_KM2 = 0.0009
CLASSES = {
    1: "cropland_km2", 2: "forest_km2", 3: "shrub_km2",
    4: "grassland_km2", 5: "water_km2", 6: "snow_km2",
    7: "barren_km2", 8: "impervious_km2", 9: "wetland_km2",
}


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def near(a, b, tolerance=1e-6):
    return bool(np.allclose(np.asarray(a, dtype=float), np.asarray(b, dtype=float),
                            atol=tolerance, rtol=0, equal_nan=False))


def audit(root):
    root = Path(root).resolve()
    errors, warnings, checks = [], [], []
    paths = {
        "catalog": root / "data/districts.csv",
        "land": root / "results/landcover/landcover_recomputed.csv",
        "change": root / "results/landcover/impervious_change.csv",
        "flow": root / "results/landcover/class_transitions.csv",
        "socio": root / "results/socioeconomic/socio_21district_4year.csv",
        "dashboard": root / "results/socioeconomic/four-year-exploratory/dashboard.json",
        "boundaries": root / "results/socioeconomic/four-year-exploratory/districts.geojson",
        "scores": root / "results/socioeconomic/four-year-exploratory/district_year.csv",
        "weights": root / "results/socioeconomic/four-year-exploratory/weights.csv",
        "sensitivity": root / "results/socioeconomic/historical_basis_sensitivity.csv",
    }
    missing = [name for name, path in paths.items() if not path.is_file()]
    if missing:
        return {"status": "failed", "errors": [f"Missing required files: {missing}"],
                "warnings": [], "checks": [], "summary": {"errors": 1, "warnings": 0, "checks": 0}}

    catalog = pd.read_csv(paths["catalog"], dtype={"code": str})
    codes = set(catalog["code"])
    catalog_ok = (len(catalog) == 21 and len(codes) == 21
                  and catalog["code"].str.fullmatch("[0-9]{6}").all()
                  and catalog.groupby("group")["code"].nunique().to_dict()
                  == {"中心城区": 9, "主城新区": 12})
    if not catalog_ok:
        errors.append("District catalog must contain 21 unique six-digit codes (9 central + 12 new-town districts).")
    expected = {(code, year) for code in codes for year in YEARS}
    checks.append({"name": "district_catalog", "status": "pass" if catalog_ok else "failed",
                   "districts": len(catalog)})

    land = pd.read_csv(paths["land"], dtype={"adcode": str})
    land_ok = (len(land) == 84 and set(zip(land.adcode, land.year)) == expected
               and not land.duplicated(["adcode", "year"]).any()
               and near(land[list(CLASSES.values())].sum(axis=1), land.valid_area_km2)
               and (land.valid_area_km2 > 0).all() and (land.nodata_area_km2 >= 0).all())
    if not land_ok:
        errors.append("Land-cover panel keys, class-area totals, or valid/NoData areas failed validation.")
    checks.append({"name": "landcover_panel", "status": "pass" if land_ok else "failed",
                   "rows": len(land), "years": sorted(land.year.unique().tolist())})

    change = pd.read_csv(paths["change"], dtype={"adcode": str})
    interval_keys = {(code, start, end) for code in codes for start, end in INTERVALS}
    change_ok = (len(change) == 63
                 and set(zip(change.adcode, change.start, change.end)) == interval_keys
                 and not change.duplicated(["adcode", "start", "end"]).any()
                 and near(change.added_km2 - change.lost_km2, change.net_km2)
                 and near(change.adjacent_km2 + change.nonadjacent_km2
                           + change.adjacency_unknown_km2, change.added_km2))
    if not change_ok:
        errors.append("Expansion interval keys or added/lost/net/morphology area reconciliation failed.")
    checks.append({"name": "expansion_reconciliation", "status": "pass" if change_ok else "failed",
                   "interval_rows": len(change)})

    flow = pd.read_csv(paths["flow"], dtype={"adcode": str})
    grouped = flow.groupby(["adcode", "start", "end"])
    flow_errors = []
    flow_shape_ok = (len(flow) == 5103 and len(grouped) == 63
                     and (grouped.size() == 81).all()
                     and flow[["from_class", "to_class"]].isin(range(1, 10)).all().all()
                     and (flow.pixel_count >= 0).all()
                     and near(flow.area_km2, flow.pixel_count * PIXEL_KM2))
    if flow_shape_ok:
        land_idx = land.set_index(["adcode", "year"])
        change_idx = change.set_index(["adcode", "start", "end"])
        for (code, start, end), cells in grouped:
            matrix = cells.pivot(index="from_class", columns="to_class", values="pixel_count")
            if matrix.shape != (9, 9) or matrix.isna().any().any():
                flow_errors.append(f"{code} {start}-{end}: incomplete matrix")
                continue
            matrix = matrix.reindex(index=range(1, 10), columns=range(1, 10))
            for klass, column in CLASSES.items():
                if not np.isclose(matrix.loc[klass].sum() * PIXEL_KM2,
                                  land_idx.loc[(code, start), column], atol=1e-6, rtol=0):
                    flow_errors.append(f"{code} {start}: class {klass} row total mismatch")
                if not np.isclose(matrix[klass].sum() * PIXEL_KM2,
                                  land_idx.loc[(code, end), column], atol=1e-6, rtol=0):
                    flow_errors.append(f"{code} {end}: class {klass} column total mismatch")
            delta = change_idx.loc[(code, start, end)]
            added = (matrix.loc[:, 8].sum() - matrix.loc[8, 8]) * PIXEL_KM2
            lost = (matrix.loc[8, :].sum() - matrix.loc[8, 8]) * PIXEL_KM2
            if not np.isclose(added, delta.added_km2, atol=1e-6, rtol=0):
                flow_errors.append(f"{code} {start}-{end}: added area mismatch")
            if not np.isclose(lost, delta.lost_km2, atol=1e-6, rtol=0):
                flow_errors.append(f"{code} {start}-{end}: lost area mismatch")
    else:
        flow_errors.append("Expected 5,103 non-negative cells in 63 complete 9×9 matrices.")
    if flow_errors:
        errors.append("Transition matrix validation failed: " + "; ".join(flow_errors[:8]))
    checks.append({"name": "transition_matrices", "status": "pass" if not flow_errors else "failed",
                   "cells": len(flow), "matrices": len(grouped), "reconciliation_errors": len(flow_errors)})

    socio = pd.read_csv(paths["socio"], dtype={"adcode": str})
    socio_ok = (len(socio) == 84 and set(zip(socio.adcode, socio.year)) == expected
                and not socio.duplicated(["adcode", "year"]).any())
    required = ["source_gdp", "source_pop", "quality_population", "quality_gdp", "quality_secondary"]
    socio_ok = socio_ok and all(col in socio and socio[col].notna().all()
                                and socio[col].astype(str).str.strip().ne("").all() for col in required)
    for col in ["quality_population", "quality_gdp", "quality_secondary"]:
        socio_ok = socio_ok and socio[col].isin(["A", "B", "C"]).all()
    recent = socio[socio.year.isin([2020, 2022])]
    recent_a = len(recent) == 42 and recent[
        ["quality_population", "quality_gdp", "quality_secondary"]
    ].eq("A").all().all()
    sector_sum = socio.primary_10k_yuan + socio.secondary_10k_yuan + socio.tertiary_10k_yuan
    socio_ok = socio_ok and recent_a and near(sector_sum, socio.gdp_10k_yuan, 1.01)
    if not socio_ok:
        errors.append("Socioeconomic panel keys, provenance grades, recent-year quality, or GDP-sector reconciliation failed.")
    warnings.extend([
        "2010/2015 GDP and secondary-industry values include B/C quality grades; four-period scores are exploratory.",
        "Economic series use nominal prices; cross-year score changes include price effects.",
        "Yearbook page references are transcribed metadata; original source scans/revision records are not archived for independent verification.",
        "Display GeoJSON is a presentation layer; area calculations rely on the native equal-area district-ID raster, not display polygon geometry.",
    ])
    checks.append({"name": "socioeconomic_panel", "status": "pass" if socio_ok else "failed",
                   "rows": len(socio), "recent_rows": len(recent), "recent_all_grade_a": bool(recent_a),
                   "quality_grades": {col: socio[col].value_counts().sort_index().to_dict()
                                      for col in ["quality_population", "quality_gdp", "quality_secondary"]}})

    dashboard = json.loads(paths["dashboard"].read_text(encoding="utf-8"))
    dashboard_ok = (len(dashboard) == 84
                    and {(str(row["code"]), int(row["year"])) for row in dashboard} == expected
                    and all(row.get("data_kind") == "observed" for row in dashboard)
                    and all(np.isfinite(row["intensive_score"]) and 0 <= row["intensive_score"] <= 1
                            for row in dashboard))
    scores = pd.read_csv(paths["scores"], dtype={"code": str})
    weights = pd.read_csv(paths["weights"])
    score_ok = len(scores) == 84 and not scores.duplicated(["code", "year"]).any()
    weights_ok = (np.isfinite(weights.weight).all() and (weights.weight >= 0).all()
                  and np.isclose(weights.weight.sum(), 1, atol=1e-8))
    if not dashboard_ok or not score_ok or not weights_ok:
        errors.append("Dashboard, score table, or entropy-weight output failed validation.")
    checks.append({"name": "evaluation_outputs",
                   "status": "pass" if dashboard_ok and score_ok and weights_ok else "failed",
                   "dashboard_rows": len(dashboard), "score_rows": len(scores),
                   "weights_sum": round(float(weights.weight.sum()), 10)})

    geojson = json.loads(paths["boundaries"].read_text(encoding="utf-8"))
    features = geojson.get("features", [])
    invalid = []
    for feature in features:
        geometry = shape(feature["geometry"])
        minx, miny, maxx, maxy = geometry.bounds
        if (geometry.geom_type not in {"Polygon", "MultiPolygon"} or geometry.is_empty
                or not geometry.is_valid or not (-180 <= minx <= maxx <= 180)
                or not (-90 <= miny <= maxy <= 90)):
            invalid.append(str(feature.get("properties", {}).get("code", "unknown")))
    boundary_ok = (geojson.get("type") == "FeatureCollection" and len(features) == 21
                   and {str(f["properties"]["code"]) for f in features} == codes and not invalid)
    if not boundary_ok:
        errors.append(f"Display GeoJSON must contain 21 valid WGS84 polygons; invalid features: {invalid[:8]}.")
    checks.append({"name": "display_boundaries", "status": "pass" if boundary_ok else "failed",
                   "features": len(features), "invalid_features": invalid})

    sensitivity_ok = len(pd.read_csv(paths["sensitivity"])) == 84
    if not sensitivity_ok:
        errors.append("Historical-basis sensitivity output must contain 84 rows.")
    manifest = {name: {"path": str(path.relative_to(root)), "bytes": path.stat().st_size,
                       "sha256": digest(path)} for name, path in paths.items()}
    status = "failed" if errors else "passed_with_warnings" if warnings else "passed"
    return {
        "schema_version": 1, "status": status,
        "study_scope": {"districts": 21, "years": list(YEARS), "intervals": [list(x) for x in INTERVALS]},
        "summary": {"checks": len(checks), "errors": len(errors), "warnings": len(warnings)},
        "checks": checks, "errors": errors, "warnings": warnings, "source_manifest": manifest,
    }


def write_report(report, output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    (output / "data-quality-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    lines = [
        "# 数据质量与可追溯性审计报告", "", f"**审计状态：{report['status']}**", "",
        f"- 研究单元：{report['study_scope']['districts']} 区",
        f"- 研究年份：{', '.join(map(str, report['study_scope']['years']))}",
        f"- 检查项：{report['summary']['checks']}",
        f"- 错误：{report['summary']['errors']}",
        f"- 数据限制提示：{report['summary']['warnings']}", "",
        "## 检查结果", "", "| 检查 | 状态 | 结果摘要 |", "|---|---|---|",
    ]
    for item in report["checks"]:
        details = ", ".join(f"{k}={v}" for k, v in item.items() if k not in {"name", "status"})
        lines.append(f"| {item['name']} | {item['status']} | {details} |")
    lines += ["", "## 必须保留的数据限制", ""]
    lines.extend(f"- {warning}" for warning in report["warnings"])
    lines += ["", "## 错误", ""]
    lines.extend(f"- {error}" for error in report["errors"])
    lines += ["", "## 文件指纹", "",
              "JSON 报告记录每份输入文件的相对路径、字节数和 SHA-256。指纹用于版本追溯，不代表源数据已获外部权威认证。", ""]
    (output / "data-quality-report.md").write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--output", type=Path, default=Path("outputs/data-audit"))
    args = parser.parse_args()
    report = audit(args.root)
    write_report(report, args.output)
    print(json.dumps(report["summary"] | {"status": report["status"]}, ensure_ascii=False))
    return 1 if report["status"] == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
