import csv
import json
import mimetypes
from pathlib import Path

from django.conf import settings
from django.core.exceptions import RequestDataTooBig
from django.db import DatabaseError
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from .models import District, Observation
from .ollama import choose_evidence
from .postgis import published_data

WEB = settings.ROOT / "web"
PAGES = {"/": "index.html", "/mobile.html": "mobile.html", "/desktop.html": "desktop.html", "/city.html": "city.html", "/dashboard3d.html": "dashboard3d.html", "/guide.html": "guide.html"}
ASSETS = {
    "app.js", "style.css", "analysis.js", "client-utils.js", "sw.js", "manifest.webmanifest",
    "mobile.js", "mobile.css", "mobile.webmanifest", "desktop.js", "desktop.css", "river-ink.webp", "rivers.geojson",
    "icon192.png", "icon512.png", "charts.js", "analytics-page.js",
    "city.js", "city.css", "vendor/maplibre-5.16.0.css", "vendor/maplibre-5.16.0.js", "vendor/maplibre-LICENSE.txt",
    "city/manifest.json", "city/buildings.geojson", "city/poi.geojson", "city/roads.geojson",
    "city/cover-2010.png", "city/cover-2015.png", "city/cover-2020.png", "city/cover-2022.png",
    "city/change-2015.png", "city/change-2020.png", "city/change-2022.png",
    "vendor/echarts-6.0.0.min.js", "vendor/echarts-LICENSE.txt", "vendor/echarts-NOTICE.txt",
    "dashboard3d.js", "dashboard3d.css", "guide.js", "guide.css",
}


@require_GET
@ensure_csrf_cookie
def page(request):
    return render(request, PAGES[request.path])


@require_GET
def asset(request, name):
    if name not in ASSETS or not (WEB / name).is_file():
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
    """Readiness probe: report ready only when the full 21-district, four-period panel is usable."""
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
            len(features) != 21 or len(codes) != 21 or len(rows) != 84
            or years != expected_years
            or keys != {(code, year) for code in codes for year in expected_years}
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
        report = json.loads(settings.ANALYSIS_REPORT.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return JsonResponse({"error": "请先运行 build_analysis。"}, status=503)
    from .provenance import panel_fingerprint
    try:
        if report.get("panel_fingerprint") != panel_fingerprint(snapshot("dashboard.json")):
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
