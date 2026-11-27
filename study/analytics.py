"""Reproducible ETL and temporal validation of district-level land expansion."""
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory

import duckdb
import numpy as np
from sklearn.cluster import KMeans
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, root_mean_squared_error, silhouette_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from .provenance import panel_fingerprint

FEATURES = {
    "baseline_area_km2": "期初不透水面面积",
    "forest_share": "期初林地比例",
    "cropland_share": "期初耕地比例",
    "water_share": "期初水体比例",
    "baseline_population": "期初常住人口",
}
TABLES = {"cover": "landcover_recomputed.csv", "change": "impervious_change.csv", "flow": "class_transitions.csv"}
FEATURE_SQL = """
SELECT c.adcode, c.district, c."group" AS region, c.start, c."end",
       p.impervious_km2 AS baseline_area_km2,
       p.forest_km2 / nullif(p.valid_area_km2, 0) AS forest_share,
       p.cropland_km2 / nullif(p.valid_area_km2, 0) AS cropland_share,
       p.water_km2 / nullif(p.valid_area_km2, 0) AS water_share,
       s.population_person AS baseline_population,
       c.net_km2 / (c."end" - c.start) AS annual_net_km2
FROM change c
JOIN cover p ON c.adcode = p.adcode AND c.start = p.year
JOIN socio s ON c.adcode = s.adcode AND c.start = s.year
ORDER BY c."end", c.adcode
"""


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def metrics(actual, predict):
    return {"mae": round(float(mean_absolute_error(actual, predict)), 6),
            "rmse": round(float(root_mean_squared_error(actual, predict)), 6)}


def machine_learning(rows):
    columns = list(FEATURES)
    train = [x for x in rows if x["end"] <= 2020]
    holdout = [x for x in rows if x["start"] == 2020 and x["end"] == 2022]
    if len(train) != 42 or len(holdout) != 21:
        raise ValueError("Expected 42 training rows and 21 temporal holdout rows.")
    x_train, x_test = (np.array([[r[k] for k in columns] for r in subset], dtype=float) for subset in (train, holdout))
    y_train, y_test = (np.array([r["annual_net_km2"] for r in subset]) for subset in (train, holdout))
    if not all(np.isfinite(a).all() for a in (x_train, x_test, y_train, y_test)):
        raise ValueError("Non-finite model inputs.")
    candidates = {
        "median": DummyRegressor(strategy="median"),
        "ridge": make_pipeline(StandardScaler(), Ridge(alpha=10)),
        "random_forest": RandomForestRegressor(
            n_estimators=250, min_samples_leaf=4, max_depth=5, random_state=42, n_jobs=1
        ),
    }
    predictions, scores = {}, {}
    for key, model in candidates.items():
        values = model.fit(x_train, y_train).predict(x_test)
        scores[key] = metrics(y_test, values)
        predictions[key] = values
    holdout_result = [{
        "code": str(row["adcode"]), "district": row["district"], "region": row["region"],
        "actual": round(float(y_test[i]), 6),
        **{key: round(float(predictions[key][i]), 6) for key in candidates},
    } for i, row in enumerate(holdout)]

    standardized = StandardScaler().fit_transform(x_test)
    groups = KMeans(n_clusters=3, n_init=30, random_state=42).fit_predict(standardized)
    labels = [{
        "district": row["district"], "code": str(row["adcode"]), "region": row["region"],
        "cluster": int(groups[i]) + 1,
        "baseline_area_km2": row["baseline_area_km2"], "baseline_population": row["baseline_population"],
    } for i, row in enumerate(holdout)]
    return {
        "features": FEATURES, "train_years": [[2010, 2015], [2015, 2020]], "holdout_years": [2020, 2022],
        "train_count": len(train), "holdout_count": len(holdout), "target_unit": "km²/年",
        "validation": "同一批区县的时间留出检验。模型仅用期初土地覆盖和人口变量。结果用于回测。",
        "scores": scores, "predictions": holdout_result,
        "clusters": {"year": 2020, "k": 3, "silhouette": round(float(silhouette_score(standardized, groups)), 6), "rows": labels},
    }


def dict_rows(connection, sql):
    result = connection.execute(sql)
    columns = [c[0] for c in result.description]
    return [dict(zip(columns, row)) for row in result.fetchall()]


def build(root, land, output):
    socio = root / "results/socioeconomic/socio_21district_4year.csv"
    dashboard = root / "results/socioeconomic/four-year-exploratory/dashboard.json"
    sources = {key: land / name for key, name in TABLES.items()} | {"socio": socio}
    output.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(":memory:") as connection, TemporaryDirectory(dir=output) as temp:
        staging = Path(temp)
        connection.execute("SET threads = 2")
        connection.execute("SET memory_limit = '512MB'")
        for table, path in sources.items():
            connection.execute(f"CREATE TABLE {table} AS SELECT * FROM read_csv_auto(?)", [str(path)])
        counts = {table: connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0] for table in sources}
        expected = {"cover": 84, "change": 63, "flow": 5103, "socio": 84}
        if counts != expected:
            raise ValueError(f"Unexpected input counts: {counts}")
        for table, keys in {"cover":"adcode, year", "socio":"adcode, year", "change":'adcode, start, "end"',
                            "flow":'adcode, start, "end", from_class, to_class'}.items():
            if connection.execute(f"SELECT count(*) FROM (SELECT {keys} FROM {table} GROUP BY {keys})").fetchone()[0] != counts[table]:
                raise ValueError(f"Duplicate keys: {table}")
        if connection.execute("SELECT count(*) FROM flow WHERE pixel_count < 0 OR abs(area_km2 - pixel_count * 0.0009) > 0.000001").fetchone()[0]:
            raise ValueError("Transition pixel counts do not reconcile with area.")
        connection.execute("CREATE TABLE features AS " + FEATURE_SQL)
        rows = dict_rows(connection, "SELECT * FROM features")
        models = machine_learning(rows)
        yearly = dict_rows(connection, """
            SELECT year, sum(impervious_km2) AS built_km2, sum(valid_area_km2) AS valid_km2,
                   sum(nodata_area_km2) AS missing_km2
            FROM cover GROUP BY year ORDER BY year
        """)
        flows = dict_rows(connection, """
            SELECT start, "end", from_class, to_class, sum(area_km2) AS area_km2
            FROM flow GROUP BY ALL ORDER BY "end", from_class, to_class
        """)
        for table in (*sources, "features"):
            connection.table(table).write_parquet(str(staging / f"{table}.parquet"), compression="zstd")
        report = {
            "schema_version": 1, "counts": counts,
            "sources": {key: {"file": value.name, "sha256": sha(value)} for key, value in sources.items()},
            "panel_fingerprint": panel_fingerprint(json.loads(dashboard.read_text(encoding="utf-8"))),
            "yearly": yearly, "flows": flows, "model": models,
        }
        (staging / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
        for source in sorted(staging.iterdir(), key=lambda p: p.suffix == ".json"):
            source.replace(output / source.name)
    return report
