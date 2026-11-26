"""Generate explicitly fictional inputs for all 21 codes and four years."""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from rasterio.transform import from_origin
from rasterio.warp import transform_geom
from shapely.geometry import box, mapping

from spatial import CRS, YEARS, run


def generate(directory):
    directory.mkdir(parents=True, exist_ok=True)
    catalog_path = Path(__file__).parent / "data/districts.csv"
    catalog = pd.read_csv(catalog_path, dtype={"code": str})
    transform = from_origin(10_250_000, 3_650_000, 30, 30)
    features, stats, rasters = [], [], {}
    for i, code in enumerate(catalog["code"]):
        col, row = (i % 7) * 24 + 2, (i // 7) * 24 + 2
        x, y = transform @ (col, row)
        geometry = mapping(box(x, y - 600, x + 600, y))
        features.append({"type": "Feature", "properties": {"code": code},
                         "geometry": transform_geom(CRS, "EPSG:4326", geometry)})
        for t, year in enumerate(YEARS):
            stats.append([code, year, 900 + i * 57 + t * 42, 2600 + i * 301 + t * 490,
                          870 + i * 98 + t * 143, "SYNTHETIC", "fictional", "fictional"])
    boundaries = directory / "boundaries.geojson"
    boundaries.write_text(json.dumps({"type": "FeatureCollection", "features": features}))
    statistics = directory / "statistics.csv"
    pd.DataFrame(stats, columns=pd.read_csv(catalog_path.with_name("socioeconomic-template.csv")).columns).to_csv(statistics, index=False)
    for t, year in enumerate(YEARS):
        array = np.ones((76, 172), dtype="uint8")
        for i in range(21):
            col, row = (i % 7) * 24 + 2, (i // 7) * 24 + 2
            size = 3 + i % 5 + t
            array[row+2:row+2+size, col+2:col+2+size] = 8
            if t:
                array[row+2, col+2] = 1
                array[row+15:row+15+t, col+15] = 8
        path = directory / f"demo-{year}.tif"
        with rasterio.open(path, "w", driver="GTiff", width=array.shape[1], height=array.shape[0],
                           count=1, dtype=array.dtype, crs=CRS, transform=transform, nodata=0) as dataset:
            dataset.write(array, 1)
        rasters[year] = path
    return boundaries, statistics, catalog_path, rasters


if __name__ == "__main__":
    inputs = generate(Path("outputs/demo-inputs"))
    run(*inputs, 8, Path("outputs/demo"), "demo")
