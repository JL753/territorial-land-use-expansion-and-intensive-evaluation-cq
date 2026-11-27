"""Context-aware, evidence-grounded assistant for the land-use research workspace."""
import re

from django.conf import settings

from .ollama import generate_answer


METRICS = {
    "built_km2": ("不透水面面积", "km²"),
    "expansion_km2": ("阶段净扩张面积", "km²"),
    "annual_expansion_intensity_pct": ("年均扩张强度", "%"),
    "annual_growth_pct": ("年均增长率", "%"),
    "population_density": ("人口承载密度", "人/km²"),
    "gdp_density": ("单位用地 GDP", "万元/km²"),
    "secondary_density": ("单位用地二产增加值", "万元/km²"),
    "intensive_score": ("集约利用得分", "分"),
}


def _fmt(value):
    try:
        number = float(value)
        return f"{number:,.3f}".rstrip("0").rstrip(".")
    except (TypeError, ValueError):
        return "暂无"


def _metric(question, context):
    aliases = [
        (("扩张强度", "强度"), "annual_expansion_intensity_pct"),
        (("净扩张", "扩张面积", "新增面积"), "expansion_km2"),
        (("建设用地", "不透水面", "面积"), "built_km2"),
        (("人口密度", "人口承载"), "population_density"),
        (("单位用地 gdp", "单位用地GDP", "gdp"), "gdp_density"),
        (("二产", "第二产业"), "secondary_density"),
        (("集约", "topsis", "得分", "排名"), "intensive_score"),
    ]
    for words, key in aliases:
        if any(word.lower() in question.lower() for word in words):
            return key
    return context.get("metric") if context.get("metric") in METRICS else "built_km2"


def build_evidence(question, context, rows, districts):
    years = sorted({int(row["year"]) for row in rows})
    year_match = re.search(r"(?<!\d)(19\d{2}|20\d{2})(?!\d)", question)
    requested_year = int(year_match.group(1)) if year_match else context.get("year")
    if requested_year is not None:
        try:
            requested_year = int(requested_year)
        except (TypeError, ValueError):
            requested_year = None
    unavailable_year = requested_year if requested_year is not None and requested_year not in years else None
    if unavailable_year is not None:
        requested_year = None

    district_names = []
    district_features = districts.get("features", []) if isinstance(districts, dict) else []
    for feature in district_features:
        props = feature.get("properties", {})
        name = props.get("district", "")
        code = str(props.get("code", ""))
        if name and name in question:
            district_names.append((code, name))
    context_code = str(context.get("district_code") or "")
    if not district_names and context.get("district_name"):
        name = str(context["district_name"]).strip()
        district_names = [(str(f.get("properties", {}).get("code", "")), f.get("properties", {}).get("district", "")) for f in district_features if f.get("properties", {}).get("district") == name]
    if context_code:
        district_names = [
            (str(f.get("properties", {}).get("code", "")), f.get("properties", {}).get("district", ""))
            for f in district_features if str(f.get("properties", {}).get("code", "")) == context_code
        ] or district_names

    metric = _metric(question, context)
    metric_name, unit = METRICS.get(metric, METRICS["built_km2"])
    filtered = list(rows)
    if unavailable_year is not None:
        filtered = []
    if requested_year:
        filtered = [row for row in filtered if int(row["year"]) == requested_year]
    if context.get("group") in {"中心城区", "主城新区"}:
        filtered = [row for row in filtered if row.get("group") == context["group"]]
    if district_names:
        codes = {code for code, _ in district_names}
        filtered = [row for row in filtered if str(row.get("code")) in codes]

    evidence = [
        "数据口径：当前已入库的研究观测数据；不是实时遥感影像。",
        f"当前数据年份：{', '.join(map(str, years))}。",
        f"当前查询指标：{metric_name}（{unit}）。",
    ]
    if not filtered:
        if unavailable_year is not None:
            evidence.append(f"请求的 {unavailable_year} 年尚未进入当前研究数据库。当前已入库年份为：{', '.join(map(str, years))}。不能用其他年份替代该年份。")
        else:
            evidence.append("当前筛选条件没有匹配记录。需先完成对应数据采集、处理和质量审计。")
    else:
        if not district_names and not any(word in question for word in ("趋势", "历年", "变化过程", "所有年份")):
            filtered.sort(key=lambda row: float(row.get(metric) or 0), reverse=True)
            filtered = filtered[:8]
        for row in filtered[:45]:
            value = row.get(metric)
            evidence.append(
                f"{row.get('district')}（{row.get('code')}）{row.get('year')}年："
                f"{metric_name}={_fmt(value)} {unit}；区组={row.get('group')}；"
                f"扩张量={_fmt(row.get('expansion_km2'))} km²；"
                f"集约得分={_fmt(row.get('intensive_score'))}。"
            )
    return evidence, {
        "years_available": years,
        "year": requested_year,
        "districts": [name for _, name in district_names],
        "metric": metric,
        "metric_label": metric_name,
    }


def answer_question(question, context, rows, districts):
    evidence, resolved = build_evidence(question, context, rows, districts)
    evidence_text = "\n".join(evidence)
    if settings.OLLAMA_MODEL:
        try:
            answer = generate_answer(
                settings.OLLAMA_MODEL, question, evidence_text,
                getattr(settings, "OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
            )
            mode = "ollama"
        except Exception:
            answer = (
                "本机大语言模型暂不可用，以下为直接从研究数据库检索的结果。\\n\\n"
                + "\\n".join(evidence[1:])
            )
            mode = "data-fallback"
    else:
        answer = (
            "我已根据当前研究数据完成检索。\n\n"
            + "\n".join(evidence[1:])
            + "\n\n当前未配置大语言模型，因此这里提供的是可核验的数据检索结果；"
            "配置 CQ_OLLAMA_MODEL 并启动 Ollama 后，可启用自然语言综合解读。"
        )
        mode = "data"
    return {"answer": answer, "evidence": evidence, "context": resolved, "mode": mode}
