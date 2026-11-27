"""Public geospatial data source registry and lightweight version checks."""
import json
import re
from urllib.request import Request, urlopen

CLCD_RECORD_ID = "18180184"
CLCD_RECORD_API = f"https://zenodo.org/api/records/{CLCD_RECORD_ID}"

SOURCES = [
    {
        "key": "clcd", "name": "CLCD 中国年度土地覆盖", "category": "土地覆盖",
        "provider": "武汉大学 · Zenodo", "coverage": "1985—2025（实际年份以文件清单为准）",
        "resolution": "30 m", "update_mode": "年度产品发布后检查新版本",
        "freshness": "年度更新，非实时遥感流", "priority": "P0",
        "url": f"https://zenodo.org/records/{CLCD_RECORD_ID}",
        "checkable": True,
        "description": "主研究土地覆盖数据；下载后按统一区划、投影和分类体系处理。",
    },
    {
        "key": "ghsl", "name": "GHSL 全球人居环境数据", "category": "建成区对照",
        "provider": "欧盟 JRC", "coverage": "多期历史产品，按产品版本",
        "resolution": "依产品而定", "update_mode": "产品发布后检查",
        "freshness": "非实时", "priority": "P1",
        "url": "https://ghsl.jrc.ec.europa.eu/",
        "checkable": False,
        "description": "用于独立对照建成区、人口和建筑环境，不与 CLCD 像元类别直接混算。",
    },
    {
        "key": "dem", "name": "Copernicus DEM GLO-30", "category": "地形高程",
        "provider": "Copernicus Data Space", "coverage": "全球",
        "resolution": "约 30 m", "update_mode": "首次下载，按产品版本维护",
        "freshness": "静态基础地形，不是实时高程", "priority": "P0",
        "url": "https://dataspace.copernicus.eu/",
        "checkable": False,
        "description": "为全域及各区县三维地形场景提供高程基础；正式入库前记录版本和许可。",
    },
    {
        "key": "osm", "name": "OpenStreetMap 建筑、道路与 POI", "category": "矢量地理要素",
        "provider": "OpenStreetMap / Geofabrik", "coverage": "持续编辑的众包数据",
        "resolution": "要素级", "update_mode": "按周或按月同步快照",
        "freshness": "可较高频更新，但不保证实时完整", "priority": "P0",
        "url": "https://download.geofabrik.de/asia/china.html",
        "checkable": False,
        "description": "用于区县建筑、道路和设施三维表达；需保留 ODbL 署名和快照日期。",
    },
    {
        "key": "statistics", "name": "重庆区县人口与经济统计", "category": "社会经济",
        "provider": "重庆市统计局 / 区县统计公报与年鉴", "coverage": "按年鉴和公报发布",
        "resolution": "区县年度统计", "update_mode": "新年鉴或统计公报发布后采集",
        "freshness": "滞后发布，非实时", "priority": "P0",
        "url": "https://tjj.cq.gov.cn/",
        "checkable": False,
        "description": "人口、GDP、产业增加值等指标需保留原始出处、单位、价格口径和区划口径。",
    },
    {
        "key": "boundaries", "name": "行政区划与研究区边界", "category": "基础地理",
        "provider": "官方公开区划资料及可核验边界数据", "coverage": "按区划版本",
        "resolution": "矢量边界", "update_mode": "区划调整时更新",
        "freshness": "低频版本更新", "priority": "P0",
        "url": "https://www.mca.gov.cn/",
        "checkable": False,
        "description": "统一 21 个研究区县的代码、名称、边界版本和面积口径。",
    },
]


def source_catalog():
    return [dict(item) for item in SOURCES]


def check_clcd():
    request = Request(CLCD_RECORD_API, headers={
        "Accept": "application/json",
        "User-Agent": "ShanchengDiyan/2.0 (research data version checker)",
    })
    with urlopen(request, timeout=15) as response:
        record = json.load(response)
    metadata = record.get("metadata", {})
    files = record.get("files", [])
    years = []
    for item in files:
        match = re.search(r"(?:19|20)\d{2}", item.get("key", ""))
        if match:
            years.append(int(match.group(0)))
    title_years = [int(value) for value in re.findall(r"(?:19|20)\d{2}", metadata.get("title", ""))]
    latest_year = max(years + title_years, default=None)
    selected_files = [{
        "name": item.get("key", ""),
        "size": item.get("size"),
        "checksum": item.get("checksum"),
        "download_url": item.get("links", {}).get("self"),
    } for item in files if "province.zip" in item.get("key", "") or "classificationsystem" in item.get("key", "")]
    return {
        "status": "success",
        "version": metadata.get("version") or metadata.get("publication_date") or "latest",
        "title": metadata.get("title", "CLCD"),
        "publication_date": metadata.get("publication_date"),
        "modified": record.get("updated"),
        "latest_year": latest_year,
        "file_count": len(files),
        "selected_files": selected_files[:12],
        "record_url": record.get("links", {}).get("html", f"https://zenodo.org/records/{CLCD_RECORD_ID}"),
    }


def check_source(key):
    if key == "clcd":
        return check_clcd()
    source = next((item for item in SOURCES if item["key"] == key), None)
    if source is None:
        raise KeyError(key)
    return {
        "status": "manual",
        "message": "该来源暂不提供无需凭据的自动版本接口；请按来源页面核验并登记版本。",
        "source_url": source["url"],
    }
