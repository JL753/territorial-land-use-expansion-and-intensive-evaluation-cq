"""Validate, publish and restore complete research and map snapshots."""
import hashlib
import json
import math
from pathlib import Path
import tempfile
from urllib.error import URLError
from urllib.parse import urlencode, urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from shapely.geometry import shape

from .models import District, MapRelease, Observation, Publication, ResearchRelease
from .provenance import panel_fingerprint

HUXI = [106.281, 29.584, 106.309, 29.606]
OSM_URL = "https://api.openstreetmap.org/api/0.6/map.json?" + urlencode({"bbox": ",".join(map(str, HUXI))})
OSM_BOOTSTRAP = ("https://raw.githubusercontent.com/zhipengGui/cqu-campus-3d/"
                 "2cfb045b0dd7118d683eebf604c3156e61241015/data/snapshots/osm_snapshot_2026-10-13.json")
REQUIRED_NUMBERS = ("built_km2", "admin_km2", "valid_area_km2", "nodata_area_km2", "population",
                    "gdp_10k_cny", "secondary_10k_cny", "cropland_km2", "forest_km2", "water_km2")
DERIVED = {"interval_start", "expansion_km2", "annual_growth_pct", "annual_expansion_intensity_pct",
           "population_density", "gdp_density", "secondary_density", "intensive_score", "equal_weight_score",
           "rank", "equal_weight_rank", "evaluation_basis", "added_km2", "lost_km2"}
LIMIT = 20 * 1024 * 1024


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def publication():
    return Publication.objects.select_related("research", "map_release").filter(pk=1).first()


def readable_source(url):
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.port not in (None, 443):
        raise ValueError("Source must be direct HTTPS without credentials.")
    return parsed.hostname + parsed.path


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *_):
        raise URLError("Redirects are disabled for publication feeds.")


def download(url, host):
    readable_source(url)
    if urlsplit(url).hostname != host:
        raise ValueError("Publication files must come from the configured source host.")
    request = Request(url, headers={"User-Agent": "ChongqingLandResearch/1.0"})
    with build_opener(NoRedirect()).open(request, timeout=25) as response:
        raw = response.read(LIMIT + 1)
    if len(raw) > LIMIT:
        raise ValueError("Source file exceeds the 20 MiB limit.")
    return raw


def load_remote_bundle(url):
    host = urlsplit(url).hostname
    manifest = json.loads(download(url, host))
    if manifest.get("schema") != 1:
        raise ValueError("Publication manifest needs schema 1.")
    output = []
    for name in ("districts.geojson", "dashboard.json"):
        entry = manifest["files"][name]
        target = urljoin(url, entry["path"])
        raw = download(target, host)
        if hashlib.sha256(raw).hexdigest() != entry["sha256"]:
            raise ValueError(f"Checksum mismatch for {name}.")
        output.append(json.loads(raw))
    return (*output, readable_source(url))


def coordinates_ok(geometry):
    form = shape(geometry)
    if form.geom_type not in {"Polygon", "MultiPolygon"} or form.is_empty or not form.is_valid:
        return False
    west, south, east, north = form.bounds
    return 103 < west <= east < 111 and 27 < south <= north < 34


def finite_nonnegative(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def validate(geo, rows):
    from csv import DictReader

    with (settings.ROOT / "data/districts.csv").open(encoding="utf-8", newline="") as stream:
        catalog = {r["code"]: (r["district"], r["group"]) for r in DictReader(stream)}
    actual = {}
    if geo["type"] != "FeatureCollection":
        raise ValueError("Expected a district FeatureCollection.")
    for item in geo["features"]:
        prop = item["properties"]
        code = str(prop["code"])
        if (code in actual or catalog.get(code) != (prop["district"], prop["group"])
                or not coordinates_ok(item["geometry"])):
            raise ValueError(f"Invalid district feature {code}.")
        actual[code] = item
    if set(actual) != set(catalog):
        raise ValueError("Expected the published 21-district catalog.")
    panel = {}
    for row in rows:
        code, year = str(row["code"]), row["year"]
        if (code not in actual or (code, year) in panel or type(year) is not int or not 2010 <= year <= timezone.localdate().year
                or catalog[code] != (row["district"], row["group"]) or row.get("data_kind") != "observed"):
            raise ValueError(f"Invalid observation ID {code}/{year}.")
        bad = [key for key in REQUIRED_NUMBERS if not finite_nonnegative(row.get(key))]
        if bad or not 0 < row["built_km2"] <= row["valid_area_km2"] + .001 or min(
                row["population"], row["admin_km2"], row["gdp_10k_cny"], row["secondary_10k_cny"]) <= 0:
            raise ValueError(f"Invalid measurements {code}/{year}: {bad}")
        if row["secondary_10k_cny"] > row["gdp_10k_cny"] or row["valid_area_km2"] + row["nodata_area_km2"] > row["admin_km2"] * 1.01:
            raise ValueError(f"Inconsistent area or economy {code}/{year}.")
        if type(row.get("provisional")) is not bool or not all(
            isinstance(row.get(field), str) and row[field].strip() for field in ("source_pop", "source_gdp")
        ):
            raise ValueError(f"Missing quality or source information {code}/{year}.")
        panel[code, year] = {**row, "code": code}
    years = sorted({year for _, year in panel})
    if not {2010, 2015, 2020, 2022}.issubset(years) or set(panel) != {(code, year) for code in actual for year in years}:
        raise ValueError("A complete comparable 21-district panel including the four original years is required.")
    for code in actual:
        for i, year in enumerate(years):
            row = panel[code, year]
            matrix = row.get("transition_km2")
            if matrix is None:
                continue
            if (not i or not isinstance(matrix, list) or len(matrix) != 9 or
                    any(not isinstance(line,list) or len(line) != 9 or not all(finite_nonnegative(v) for v in line) for line in matrix)):
                raise ValueError(f"Invalid land-transition matrix {code}/{year}.")
            prior = panel[code, years[i - 1]]
            gain = sum(line[7] for j, line in enumerate(matrix) if j != 7)
            loss = sum(v for j, v in enumerate(matrix[7]) if j != 7)
            if abs(gain - loss - (row["built_km2"] - prior["built_km2"])) > .002:
                raise ValueError(f"Land transitions do not balance {code}/{year}.")
    return [panel[key] for key in sorted(panel)]


def source_identity(geo, rows):
    return digest({"districts": geo, "observations": [
        {k: v for k, v in r.items() if k not in DERIVED} for r in rows
    ]})


def recompute(rows):
    import pandas as pd
    from threadpoolctl import threadpool_limits
    from evaluate import evaluate

    frame = pd.DataFrame(rows).sort_values(["code", "year"]).reset_index(drop=True)
    if frame.groupby("code")["admin_km2"].nunique().gt(1).any():
        raise ValueError("A comparable series requires constant district areas.")
    updated, weights = evaluate(frame)
    normalized = json.loads(updated.to_json(orient="records", force_ascii=False, double_precision=14))
    for row in normalized:
        row["evaluation_basis"] = "nominal_release_exploratory"
        matrix = row.get("transition_km2")
        row["added_km2"] = sum(line[7] for i, line in enumerate(matrix) if i != 7) if matrix else None
        row["lost_km2"] = sum(v for i, v in enumerate(matrix[7]) if i != 7) if matrix else None
    from .analytics import machine_learning

    stages, annual, balances = [], {}, {}
    previous = {}
    for row in normalized:
        sums = annual.setdefault(row["year"], {"year": row["year"], "built_km2": 0, "valid_km2": 0, "missing_km2": 0})
        for target, key in [("built_km2","built_km2"),("valid_km2","valid_area_km2"),("missing_km2","nodata_area_km2")]:
            sums[target] += row[key]
        start, end = row["interval_start"], row["year"]
        prior = previous.get(row["code"])
        if prior and start is not None:
            stages.append({"adcode": row["code"], "district": row["district"], "region": row["group"], "start": start, "end": end,
                "baseline_area_km2": prior["built_km2"], "forest_share": prior["forest_km2"]/prior["valid_area_km2"],
                "cropland_share": prior["cropland_km2"]/prior["valid_area_km2"], "water_share": prior["water_km2"]/prior["valid_area_km2"],
                "baseline_population": prior["population"], "annual_net_km2": row["expansion_km2"]/(end-start)})
        previous[row["code"]] = row
        if matrix := row.get("transition_km2"):
            grouped = balances.setdefault((start, end), [0, [[0.0] * 9 for _ in range(9)]])
            grouped[0] += 1
            for i in range(9):
                for j in range(9):
                    grouped[1][i][j] += matrix[i][j]
    flows = [{"start": start, "end": end, "from_class": i+1, "to_class": j+1, "area_km2": matrix[i][j]}
             for (start, end), (count, matrix) in sorted(balances.items()) if count == 21 for i in range(9) for j in range(9)]
    with threadpool_limits(limits=2):
        model = machine_learning(stages, rolling=True)
    report = {"schema_version": 1, "counts": {"cover": len(rows), "change": len(stages), "flow": sum(
                  count*81 for count, _ in balances.values()), "socio": len(rows)}, "weights": weights.to_dict(),
              "panel_fingerprint": panel_fingerprint(normalized), "yearly": list(annual.values()), "flows": flows, "model": model}
    return normalized, report


def current_orm_data():
    geo = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {"code": row.code, "district": row.name, "group": row.region},
         "geometry": row.geometry} for row in District.objects.order_by("code")]}
    obs = list(Observation.objects.order_by("district_id", "year").values_list("payload", flat=True))
    return geo, obs


def materialize(release):
    Observation.objects.all().delete()
    District.objects.all().delete()
    District.objects.bulk_create([
        District(code=f["properties"]["code"], name=f["properties"]["district"], region=f["properties"]["group"], geometry=f["geometry"])
        for f in release.districts["features"]
    ])
    Observation.objects.bulk_create([Observation(district_id=r["code"], year=r["year"], payload=r) for r in release.observations])


def publish_research(geo, raw_rows, source):
    rows = validate(geo, raw_rows)
    identity = source_identity(geo, rows)
    active = publication()
    if active and active.research_id and active.research.digest == identity:
        return active.research, False
    normalized, report = recompute(rows)
    report["sources"] = {"publication": {"file": source, "sha256": identity}}
    with transaction.atomic():
        pointer, _ = Publication.objects.select_for_update().get_or_create(pk=1)
        if not pointer.research_id:
            prior_geo, prior_rows = current_orm_data()
            if prior_rows:
                historical_report = json.loads(settings.ANALYSIS_REPORT.read_text()) if settings.ANALYSIS_REPORT.is_file() else None
                baseline_id = digest({"previous": prior_geo, "observations": prior_rows})
                ResearchRelease.objects.get_or_create(digest=baseline_id, defaults={
                    "source":"仓库基线","districts":prior_geo,"observations":prior_rows,"report":historical_report})
        release, _ = ResearchRelease.objects.get_or_create(digest=identity, defaults={
            "source":source, "districts":geo, "observations":normalized, "report":report})
        if pointer.research_id == release.pk:
            return release, False
        if pointer.research_id:
            previous_years = {r["year"] for r in pointer.research.observations}
            incoming_years = {r["year"] for r in rows}
            if not previous_years.issubset(incoming_years):
                raise ValueError("Publishing cannot remove an observed year. Use explicit restore.")
            if release.published_at < pointer.research.published_at:
                raise ValueError("Use explicit restore to activate an earlier known publication.")
        materialize(release)
        pointer.research = release
        pointer.save(update_fields=["research"])
    return release, True


def restore_research(version):
    with transaction.atomic():
        release = ResearchRelease.objects.get(pk=version)
        pointer, _ = Publication.objects.select_for_update().get_or_create(pk=1)
        materialize(release)
        pointer.research = release
        pointer.save(update_fields=["research"])
    return release


def refresh_map(bootstrap=False):
    from tools.build_city_layers import osm_layers

    url = OSM_BOOTSTRAP if bootstrap else OSM_URL
    raw = json.loads(download(url, urlsplit(url).hostname))
    if not isinstance(raw.get("elements"), list) or not raw["elements"]:
        raise ValueError("Empty or invalid OSM snapshot.")
    raw.update(bbox=HUXI, fetched_at=raw.get("fetched_at") or timezone.now().isoformat())
    with tempfile.TemporaryDirectory() as directory:
        source = Path(directory) / "source.json"
        source.write_text(json.dumps(raw), encoding="utf-8")
        manifest = osm_layers(source, Path(directory))
        payload = {name: json.loads((Path(directory)/f"{name}.geojson").read_text()) for name in ("buildings","poi","roads")}
        identity = digest(payload)
        payload["osm"] = manifest
    if not manifest["buildings"] or not manifest["roads"]:
        raise ValueError("Snapshot is missing expected buildings or roads.")
    with transaction.atomic():
        pointer, _ = Publication.objects.select_for_update().get_or_create(pk=1)
        if bootstrap and pointer.map_release_id and pointer.map_release.digest != identity:
            raise ValueError("An active map version exists. A historical seed cannot replace it.")
        release, _ = MapRelease.objects.get_or_create(digest=identity, defaults={"source": readable_source(url), "payload": payload})
        changed = pointer.map_release_id != release.pk
        if changed:
            pointer.map_release = release
            pointer.save(update_fields=["map_release"])
    return release, changed


def restore_map(version):
    with transaction.atomic():
        release = MapRelease.objects.get(pk=version)
        pointer, _ = Publication.objects.select_for_update().get_or_create(pk=1)
        pointer.map_release = release
        pointer.save(update_fields=["map_release"])
    return release
