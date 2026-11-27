import csv
import json
import mimetypes
import re
from pathlib import Path

from django.conf import settings
from django.core.exceptions import RequestDataTooBig
from django.db import DatabaseError
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from .models import District, Observation, MapRelease, RefreshRun, ResearchRelease
from .updates import check_clcd_version, publication
from .ollama import choose_evidence
from .postgis import published_data

WEB = settings.ROOT / "web"
PAGES = {"/": "index.html", "/mobile.html": "mobile.html", "/desktop.html": "desktop.html", "/city.html": "city.html", "/dashboard3d.html": "dashboard3d.html", "/guide.html": "guide.html", "/data-center.html": "data-center.html", "/district.html": "district.html"}
ASSETS = {
    "app.js", "style.css", "analysis.js", "client-utils.js", "sw.js", "manifest.webmanifest",
    "mobile.js", "mobile.css", "mobile.webmanifest", "desktop.js", "desktop.css", "river-ink.webp", "rivers.geojson",
    "icon192.png", "icon512.png", "charts.js", "analytics-page.js",
    "city.js", "city.css", "vendor/maplibre-5.16.0.css", "vendor/maplibre-5.16.0.js", "vendor/maplibre-LICENSE.txt",
    "city/manifest.json", "city/buildings.geojson", "city/poi.geojson", "city/roads.geojson",
    "city/cover-2010.png", "city/cover-2015.png", "city/cover-2020.png", "city/cover-2022.png",
    "city/change-2015.png", "city/change-2020.png", "city/change-2022.png",
    "vendor/echarts-6.0.0.min.js", "vendor/echarts-LICENSE.txt", "vendor/echarts-NOTICE.txt",
    "live.js", "live.css", "data-center.js", "data-center.css", "district.js", "district.css", "chongqing-relief-bg.svg",
    "dashboard3d.js", "dashboard3d.css", "guide.js", "guide.css",
}


@require_GET
@ensure_csrf_cookie
def page(request):
    return render(request, PAGES[request.path])


@require_GET
def asset(request, name):
    raster_preview = re.fullmatch(r"city/(cover|change)-20[0-9]{2}\.png", name)
    if (name not in ASSETS and not raster_preview) or not (WEB / name).is_file():
        raise Http404
    content_type = "application/manifest+json" if name.endswith(".webmanifest") else mimetypes.guess_type(name)[0]
    return FileResponse((WEB / name).open("rb"), content_type=content_type or "application/octet-stream")


def snapshot(name):
    if settings.RESULT_OVERRIDE:
        return json.loads((Path(settings.RESULT_OVERRIDE) / name).read_text(encoding="utf-8"))
    if settings.USE_POSTGIS:
        return published_data(name)
    if name == "dashboard.json":
        return list(Observation.objects.values_list("payload", flat=True))
    return {"type": "FeatureCollection", "features": [
        {"type": "Feature", "geometry": d.geometry, "properties": {
            "code": d.code, "district": d.name, "group": d.region,
        }} for d in District.objects.order_by("code")
    ]}


@require_GET
def health(request):
    """Readiness probe: report ready only when a comparable 21-district panel with the initial periods is usable."""
    try:
        boundary_data = snapshot("districts.geojson")
        rows = snapshot("dashboard.json")
        features = boundary_data.get("features", []) if isinstance(boundary_data, dict) else []
        codes = {
            str(feature["properties"]["code"])
            for feature in features
            if isinstance(feature, dict) and isinstance(feature.get("properties"), dict)
        }
        years = sorted({row["year"] for row in rows})
        keys = {(str(row["code"]), row["year"]) for row in rows}
        expected_years = [2010, 2015, 2020, 2022]
        if (
            len(features) != 21 or len(codes) != 21 or len(rows) != 21 * len(years)
            or not set(expected_years).issubset(years)
            or keys != {(code, year) for code in codes for year in years}
        ):
            raise ValueError("The published study panel is incomplete.")
    except (DatabaseError, ValueError, OSError, KeyError, TypeError, AttributeError):
        return JsonResponse(
            {"status": "not_ready", "error": "研究数据尚未完成初始化或完整性校验。"},
            status=503,
        )
    return JsonResponse({
        "status": "ok",
        "districts": len(codes),
        "observations": len(rows),
        "years": years,
    })


@require_GET
def data(request, name):
    try:
        result = snapshot(name)
    except (DatabaseError, ValueError, OSError):
        return JsonResponse({"error": "研究数据暂不可用。"}, status=503)
    if not result or (name == "districts.geojson" and not result.get("features")):
        return JsonResponse({"error": "请先运行 Django 迁移和 import_study。"}, status=503)
    return JsonResponse(result, safe=isinstance(result, dict), json_dumps_params={"ensure_ascii": False})


@require_GET
def observations(request):
    year, code = request.GET.get("year"), request.GET.get("district")
    if ((year and (not year.isascii() or not year.isdigit() or len(year) != 4))
            or (code and (not code.isascii() or not code.isdigit() or len(code) != 6))):
        return JsonResponse({"error": "年份须为四位数字，区县代码须为六位数字。"}, status=400)
    try:
        if settings.RESULT_OVERRIDE or settings.USE_POSTGIS:
            rows = [row for row in snapshot("dashboard.json") or []
                    if (not year or row["year"] == int(year)) and (not code or str(row["code"]) == code)]
        else:
            query = Observation.objects.all()
            if year:
                query = query.filter(year=int(year))
            if code:
                query = query.filter(district_id=code)
            rows = list(query.values_list("payload", flat=True))
    except (DatabaseError, ValueError, OSError):
        return JsonResponse({"error": "研究数据暂不可用。"}, status=503)
    return JsonResponse({"count": len(rows), "results": rows}, json_dumps_params={"ensure_ascii": False})


@require_GET
def recent_observations(request):
    """Return the independently quality-screened 2020/2022 evaluation sample."""
    if settings.RESULT_OVERRIDE or settings.USE_POSTGIS:
        return JsonResponse(
            {"error": "当前数据源未绑定本项目的主要比较样本。"},
            status=404,
        )
    active = publication()
    if active and active.research_id and active.research.source != "仓库基线":
        return JsonResponse({"error":"当前版本使用独立重算的区年评价。"}, status=409)
    source = (
        settings.ROOT / "results" / "socioeconomic"
        / "recent-year-comparison" / "district_year.csv"
    )
    try:
        with source.open("r", encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
    except (OSError, csv.Error):
        return JsonResponse({"error": "主要比较样本暂不可用。"}, status=503)
    return JsonResponse(
        {"count": len(rows), "results": rows},
        json_dumps_params={"ensure_ascii": False},
    )


@require_GET
def analysis_report(request):
    if settings.RESULT_OVERRIDE or settings.USE_POSTGIS:
        return JsonResponse({"error": "当前数据入口使用单独的统计口径。"}, status=404)
    try:
        active = publication()
        report = active.research.report if active and active.research_id else json.loads(settings.ANALYSIS_REPORT.read_text(encoding="utf-8"))
        if not report:
            raise ValueError("Missing report.")
    except (OSError, ValueError):
        return JsonResponse({"error": "请先运行 build_analysis。"}, status=503)
    from .provenance import panel_fingerprint
    try:
        if report.get("panel_fingerprint") != panel_fingerprint(active.research.observations if active and active.research_id else snapshot("dashboard.json")):
            return JsonResponse({"error": "当前面板和分析报告不属于同一数据版本。"}, status=409)
    except (DatabaseError, ValueError, OSError):
        return JsonResponse({"error": "研究数据暂不可用。"}, status=503)
    return JsonResponse(report, json_dumps_params={"ensure_ascii": False})


@require_GET
def config(request):
    return JsonResponse({"model": settings.OLLAMA_MODEL})


@require_POST
def interpret(request):
    if not settings.OLLAMA_MODEL:
        raise Http404
    if request.content_type != "application/json":
        return JsonResponse({"error": "请发送 JSON 请求。"}, status=415)
    try:
        payload = json.loads(request.body)
        question, evidence = payload["question"], payload["evidence"]
        if not isinstance(question, str) or not isinstance(evidence, str) or not 0 < len(question) <= 400:
            raise ValueError
        lines = [line.strip() for line in evidence.splitlines() if line.strip()][:40]
        if not lines:
            raise ValueError
    except RequestDataTooBig:
        return JsonResponse({"error": "请求过大。"}, status=413)
    except (ValueError, TypeError, KeyError):
        return JsonResponse({"error": "请求内容无效。"}, status=400)
    try:
        return JsonResponse({"answer": choose_evidence(settings.OLLAMA_MODEL, question, lines)})
    except (OSError, ValueError, KeyError, TypeError):
        return JsonResponse({"error": "请检查本机 Ollama 服务和模型名称。"}, status=503)


@require_GET
def live_status(request):
    if settings.RESULT_OVERRIDE or settings.USE_POSTGIS:
        return JsonResponse({"error": "当前入口读取独立快照。"}, status=404)
    try:
        active = publication()
        research = active.research if active else None
        map_release = active.map_release if active else None
        rows = research.observations if research else snapshot("dashboard.json")
        runs = list(RefreshRun.objects.order_by("-happened_at","-pk").values("feed","status","happened_at")[:10])
        return JsonResponse({
            "research": {"id": research.pk if research else None, "source": research.source if research else "仓库基线",
                         "published_at": research.published_at if research else None,
                         "years": sorted({row["year"] for row in rows}), "observations": len(rows)},
            "map": {"id": map_release.pk if map_release else None,
                    "observed_at": map_meta.get("date") or (map_release.published_at.isoformat() if map_release else "未记录"),
                    "published_at": map_release.published_at if map_release else None},
            "versions": list(ResearchRelease.objects.order_by("-published_at").values("id","source","published_at")[:12]),
            "map_versions": list(MapRelease.objects.order_by("-published_at").values("id","source","published_at")[:12]),
            "runs": runs, "panel_feed": bool(settings.RESEARCH_FEED_URL), "model": bool(settings.OLLAMA_MODEL),
        })
    except (DatabaseError, OSError):
        return JsonResponse({"error": "更新记录暂不可用。"}, status=503)


@require_GET
def live_panel(request):
    try:
        active = None if settings.RESULT_OVERRIDE or settings.USE_POSTGIS else publication()
        release = active.research if active else None
        if release:
            rows, version = release.observations, str(release.pk)
        else:
            rows, version = snapshot("dashboard.json"), "base"
        if not rows:
            raise ValueError("Empty snapshot.")
    except (DatabaseError, ValueError, OSError):
        return JsonResponse({"error": "区年面板暂不可用。"}, status=503)
    response = JsonResponse({"version": version, "observations": rows}, json_dumps_params={"ensure_ascii": False})
    response["Cache-Control"] = "no-store"
    return response


@require_GET
def live_map(request):
    try:
        active = publication()
        release = active.map_release if active else None
        if not release:
            return JsonResponse({"error": "使用内置虎溪地图快照。"}, status=404)
        response = JsonResponse({**release.payload, "version": release.pk}, json_dumps_params={"ensure_ascii": False})
        response["Cache-Control"] = "no-store"
        return response
    except DatabaseError:
        return JsonResponse({"error": "更新图层暂不可用。"}, status=503)


@require_GET
def data_sources(request):
    active = publication()
    research = active.research if active and active.research_id else None
    map_release = active.map_release if active and active.map_release_id else None
    runs = list(RefreshRun.objects.order_by("-happened_at", "-pk").values("feed", "status", "detail", "happened_at")[:30])
    latest_clcd = next((run for run in runs if run["feed"] == "clcd"), None)
    rows = research.observations if research else snapshot("dashboard.json")
    map_meta = map_release.payload.get("osm", {}) if map_release else {}
    return JsonResponse({
        "sources": [
            {"key": "clcd", "name": "CLCD 年度土地覆盖", "category": "土地覆盖",
             "coverage": "1985—2025 产品期；实际年份按 Zenodo 文件清单识别", "resolution": "30 m",
             "freshness": "年度产品，非实时遥感流", "mode": "每 6 小时检查公开版本元数据",
             "status": latest_clcd["status"] if latest_clcd else "尚未检查",
             "latest_check": latest_clcd["happened_at"] if latest_clcd else None,
             "url": "https://zenodo.org/records/18180184"},
            {"key": "osm", "name": "OpenStreetMap 建筑、道路与 POI", "category": "矢量地理要素",
             "coverage": "当前虎溪研究框；全域区县数据待扩展", "resolution": "要素级",
             "freshness": "按 6 小时计划检查，受公开服务限流影响", "mode": "定时同步快照",
             "status": next((run["status"] for run in runs if run["feed"] == "osm"), "尚未检查"),
             "latest_check": next((run["happened_at"] for run in runs if run["feed"] == "osm"), None),
             "url": "https://www.openstreetmap.org/"},
            {"key": "research", "name": "重庆区县年度统计面板", "category": "社会经济与评价",
             "coverage": "当前已发布区县年份：" + "、".join(map(str, sorted({row["year"] for row in rows}))),
             "resolution": "21 区县 × 年份", "freshness": "批准的数据包或 HTTPS 清单发布后更新",
             "mode": "版本化发布、质量校验、人工确认",
             "status": next((run["status"] for run in runs if run["feed"] == "research"), "仓库基线"),
             "latest_check": next((run["happened_at"] for run in runs if run["feed"] == "research"), None),
             "url": "https://tjj.cq.gov.cn/"},
            {"key": "terrain", "name": "AWS Terrain Tiles / Terrarium", "category": "当前三维地形",
             "coverage": "全球瓦片服务", "resolution": "视瓦片缩放级别而定",
             "freshness": "静态地形瓦片，非实时高程", "mode": "在线按需读取",
             "status": "区县三维场景正在使用", "latest_check": None,
             "url": "https://registry.opendata.aws/terrain-tiles/"},
            {"key": "dem", "name": "Copernicus DEM GLO-30", "category": "本地高程数据",
             "coverage": "全球", "resolution": "约 30 m",
             "freshness": "静态地形产品，非实时", "mode": "下载后版本化入库",
             "status": "待接入本地 DEM 处理流水线", "latest_check": None,
             "url": "https://dataspace.copernicus.eu/"},
            {"key": "ghsl", "name": "GHSL 全球人居环境数据", "category": "独立对照",
             "coverage": "多期全球产品", "resolution": "依产品而定",
             "freshness": "按产品版本更新", "mode": "发布后人工核验",
             "status": "来源已登记", "latest_check": None,
             "url": "https://ghsl.jrc.ec.europa.eu/"},
        ],
        "research": {"version": research.pk if research else None,
                     "years": sorted({row["year"] for row in rows}), "observations": len(rows),
                     "source": research.source if research else "仓库基线"},
        "map": {"version": map_release.pk if map_release else None,
                "observed_at": map_release.payload["osm"]["date"] if map_release else "2026-10-13"},
        "runs": runs,
    }, json_dumps_params={"ensure_ascii": False})


@require_POST
def check_data_updates(request):
    try:
        details = check_clcd_version()
        detail = (
            f"CLCD {details['version']} · 最新栅格年份 {details['latest_year']} · "
            f"{len(details['available_years'])} 个年份文件 · "
            f"可用年份：{', '.join(map(str, details['available_years']))}"
        )
        RefreshRun.objects.create(feed="clcd", status="checked", detail=detail)
        return JsonResponse({"status": "checked", "detail": detail, "source": details},
                            json_dumps_params={"ensure_ascii": False})
    except Exception as exc:
        detail = f"CLCD version check: {type(exc).__name__}: {str(exc)[:300]}"
        RefreshRun.objects.create(feed="clcd", status="failed", detail=detail)
        return JsonResponse({"error": "CLCD 版本检查失败；现有已发布数据保持不变。", "detail": detail}, status=502)


@require_GET
def landcover_series(request):
    """Return the separately audited CLCD remote-sensing series, if generated."""
    path = settings.CLCD_SERIES_PATH
    if not path.is_file():
        return JsonResponse({
            "schema": 1, "status": "not_built", "years": [], "rows": [],
            "message": "CLCD 年度栅格尚未处理。运行 python tools/build_clcd_district_series.py。",
        }, json_dumps_params={"ensure_ascii": False})
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("schema") != 1 or payload.get("status") != "ready":
            raise ValueError("Unsupported CLCD series schema.")
        rows = payload.get("rows", [])
        years = payload.get("source", {}).get("years", [])
        if not rows or not years or len(rows) != len(years) * 21:
            raise ValueError("CLCD series is incomplete; expected 21 districts for every selected year.")
    except (OSError, ValueError, TypeError, KeyError) as exc:
        return JsonResponse({"status": "invalid", "error": str(exc)}, status=503)
    response = JsonResponse(payload, json_dumps_params={"ensure_ascii": False})
    response["Cache-Control"] = "no-store"
    return response


@require_GET
def osm_status(request):
    manifest_path = settings.OSM_OUTPUT_DIR / "manifest.json"
    if not manifest_path.is_file():
        return JsonResponse({"status": "not_built", "counts": {}, "snapshot_date": None})
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("schema") != 1 or len(manifest.get("districts", [])) != 21:
            raise ValueError("Invalid 21-district OSM manifest.")
        return JsonResponse({
            "status": "ready", "snapshot_date": manifest.get("snapshot_date"),
            "generated_at": manifest.get("generated_at"), "license": manifest.get("license"),
            "pbf_sha256": manifest.get("pbf_sha256"), "counts": manifest.get("counts", {}),
        }, json_dumps_params={"ensure_ascii": False})
    except (OSError, ValueError, TypeError) as exc:
        return JsonResponse({"status": "invalid", "error": str(exc)}, status=503)


@require_GET
def osm_layer(request, layer, code):
    if layer not in {"buildings", "roads", "poi"} or not re.fullmatch(r"\d{6}", code):
        raise Http404
    path = settings.OSM_OUTPUT_DIR / f"{layer}_{code}.geojson"
    if not path.is_file():
        raise Http404
    response = FileResponse(path.open("rb"), content_type="application/geo+json")
    response["Cache-Control"] = "public, max-age=3600"
    response["X-Content-Type-Options"] = "nosniff"
    return response
