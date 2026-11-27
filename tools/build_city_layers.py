"""Create licensed site overlays and compressed CLCD previews for the 3D research screen."""
import argparse
import json
import re
from collections import Counter
from pathlib import Path

import numpy as np
from PIL import Image
import rasterio
from rasterio.transform import from_bounds
from rasterio.warp import reproject, Resampling, transform, transform_bounds
from shapely.geometry import Polygon


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")


def feature(kind, coordinates, props):
    return {"type": "Feature", "geometry": {"type": kind, "coordinates": coordinates}, "properties": props}


def collection(features):
    return {"type": "FeatureCollection", "features": features}


def positive(tag):
    match = re.fullmatch(r"(\d+(?:\.\d+)?)\s*(?:m)?", str(tag or "").strip())
    return float(match[1]) if match and 0 < float(match[1]) < 1200 else None


BUILDING_USE = {
    "residential": "居住", "apartments": "居住", "dormitory": "居住",
    "retail": "商业", "commercial": "商业", "university": "教育", "school": "教育",
}
POI_TYPES = {
    "university": "教育", "school": "教育", "kindergarten": "教育", "library": "教育",
    "hospital": "医疗", "clinic": "医疗", "pharmacy": "医疗", "doctors": "医疗",
    "park": "公园与运动", "garden": "公园与运动", "sports_centre": "公园与运动",
    "swimming_pool": "公园与运动", "pitch": "公园与运动", "playground": "公园与运动",
    "bus_stop": "公共交通", "station": "公共交通", "subway_entrance": "公共交通",
    "platform": "公共交通", "bus_station": "公共交通",
    "restaurant": "生活服务", "cafe": "生活服务", "marketplace": "生活服务", "convenience": "生活服务",
    "supermarket": "生活服务", "post_office": "生活服务",
}


def osm_layers(source, out):
    data = json.loads(Path(source).read_text(encoding="utf-8"))
    nodes = {e["id"]: (e["lon"], e["lat"]) for e in data["elements"] if e["type"] == "node"}
    buildings, points, roads = [], [], []
    for item in data["elements"]:
        tags, kind = item.get("tags", {}), item["type"]
        if not tags or kind not in {"node", "way"}:
            continue
        ident = f"{kind}/{item['id']}"
        if kind == "node":
            center, ring = nodes[item["id"]], []
        else:
            if any(n not in nodes for n in item["nodes"]):
                continue
            ring = [nodes[n] for n in item["nodes"]]
            if len(ring) < 2:
                continue
            center = ring[0]
        closed = len(ring) >= 4 and ring[0] == ring[-1]
        polygon = Polygon(ring) if closed else None
        if polygon is not None and polygon.is_valid and not polygon.is_empty:
            p = polygon.representative_point()
            center = (p.x, p.y)
            if tags.get("building") and tags["building"] != "no":
                height, levels = positive(tags.get("height")), positive(tags.get("building:levels"))
                basis = "源高度标签" if height else "按楼层估算" if levels else "示意拉伸"
                buildings.append(feature("Polygon", [ring], {
                    "id": ident, "name": tags.get("name", "未命名建筑"),
                    "type": BUILDING_USE.get(tags["building"], "其他或未标注"),
                    "height": height or (levels * 3.2 if levels else 9),
                    "basis": basis, "levels": levels or 0,
                    "lon": center[0], "lat": center[1],
                }))
        if kind == "way" and tags.get("highway") in {
            "trunk", "primary", "secondary", "tertiary", "residential", "service", "unclassified"
        }:
            roads.append(feature("LineString", ring, {"name": tags.get("name", ""), "type": tags["highway"]}))
        poi = next((tag for key in ("amenity", "leisure", "railway", "highway", "public_transport", "shop")
                    if (tag := tags.get(key)) in POI_TYPES), None)
        if poi:
            points.append(feature("Point", center, {
                "id": ident, "name": tags.get("name", "未命名设施"), "type": POI_TYPES[poi], "tag": poi,
            }))
    for name, items in [("buildings", buildings), ("poi", points), ("roads", roads)]:
        write_json(out / (name + ".geojson"), collection(items))
    return {"date": data["fetched_at"], "bbox": data["bbox"], "buildings": len(buildings),
            "poi": len(points), "roads": len(roads),
            "height_basis": dict(Counter(f["properties"]["basis"] for f in buildings))}


YEARS = [2010, 2015, 2020, 2022]
COLORS = ["#d6d85f", "#4f875f", "#8ca671", "#adc582", "#5598b5", "#e3eef9", "#b39d7c", "#d37554", "#4fbbb1"]


def land_layers(root, out):
    rasters = root / "rasters"
    with rasterio.open(rasters / "CQ_Metro21_district_id.tif") as mask:
        left, bottom, right, top = transform_bounds(mask.crs, "EPSG:3857", *mask.bounds, densify_pts=21)
        w, h = 1250, round(1250 * (top-bottom) / (right-left))
        grid = from_bounds(left, bottom, right, top, w, h)
        settings = {"dst_transform": grid, "dst_crs": "EPSG:3857", "dst_nodata": 0,
                    "resampling": Resampling.nearest}
        district = np.zeros((h, w), dtype="uint8")
        reproject(rasterio.band(mask, 1), district, **settings)

    palette = np.zeros((10, 4), dtype="uint8")
    for i, color in enumerate(COLORS, 1):
        palette[i] = [*bytes.fromhex(color[1:]), 225]
    transition = np.array([[0, 0, 0, 0], [242, 119, 49, 255], [119, 206, 224, 255]], dtype="uint8")
    prior = None
    for year in YEARS:
        current = np.zeros_like(district)
        with rasterio.open(rasters / f"CQ_Metro21_LC_{year}.tif") as source:
            reproject(rasterio.band(source, 1), current, **settings)
        current[(district < 1) | (district > 21) | (current > 9)] = 0
        Image.fromarray(palette[current]).save(out / f"cover-{year}.png", optimize=True)
        if prior is not None:
            gain = (current == 8) & (prior != 8) & (prior != 0)
            loss = (prior == 8) & (current != 8) & (current != 0)
            Image.fromarray(transition[gain.astype("uint8") + 2 * loss]).save(out / f"change-{year}.png", optimize=True)
        prior = current
    x, y = transform("EPSG:3857", "EPSG:4326", [left,right,right,left], [top,top,bottom,bottom])
    return {"corners": list(zip(x, y)), "years": YEARS, "colors": COLORS, "pixels": [w,h]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clcd", type=Path, required=True)
    parser.add_argument("--osm", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("web/city"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    osm = osm_layers(args.osm, args.output)
    land = land_layers(args.clcd, args.output)
    write_json(args.output / "manifest.json", {"osm": osm, "land": land})
    print(osm)
