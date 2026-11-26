"use strict";

const el = id => document.getElementById(id);
const canvas = el("map");
const ctx = canvas.getContext("2d");
const year = el("year");
const metric = el("metric");
const group = el("group");
const status = el("status");
const fmt = new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 4 });
const display = value => value == null ? "—" : fmt.format(value);
let records = [], features = [], paths = [], selected = null;

function polygons(feature) {
  return feature.geometry.type === "Polygon" ? [feature.geometry.coordinates] : feature.geometry.coordinates;
}

function buildPaths() {
  const points = features.flatMap(feature => polygons(feature).flat(2));
  const bounds = points.reduce(([w, s, e, n], [x, y]) =>
    [Math.min(w, x), Math.min(s, y), Math.max(e, x), Math.max(n, y)],
    [Infinity, Infinity, -Infinity, -Infinity]);
  const [west, south, east, north] = bounds;
  const longitudeScale = Math.cos((north + south) * Math.PI / 360);
  const scale = Math.min((canvas.width - 36) / ((east - west) * longitudeScale),
    (canvas.height - 36) / (north - south));
  const cx = (west + east) / 2;
  const cy = (south + north) / 2;
  paths = features.map(feature => {
    const path = new Path2D();
    for (const polygon of polygons(feature)) {
      for (const ring of polygon) {
        ring.forEach(([lon, lat], index) => {
          const x = canvas.width / 2 + (lon - cx) * longitudeScale * scale;
          const y = canvas.height / 2 - (lat - cy) * scale;
          if (index === 0) path.moveTo(x, y);
          else path.lineTo(x, y);
        });
        path.closePath();
      }
    }
    return { code: feature.properties.code, path };
  });
}

function render() {
  const key = metric.value;
  const active = records.filter(row => row.year === Number(year.value) && (!group.value || row.group === group.value));
  const byCode = new Map(active.map(row => [row.code, row]));
  const values = active.map(row => row[key]).filter(Number.isFinite);
  const min = Math.min(...values), max = Math.max(...values);
  el("legend").textContent = values.length ? `浅 → 深　${display(min)} 至 ${display(max)}　灰色表示无数据或未选区域` : "该年份没有此指标区间。";
  el("value-label").textContent = metric.selectedOptions[0].textContent;
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  for (const { code, path } of paths) {
    const value = byCode.get(code)?.[key];
    const step = min === max ? 0.5 : (value - min) / (max - min);
    ctx.fillStyle = value == null ? "#cdd9d4" : `hsl(160 49% ${86 - step * 57}%)`;
    ctx.fill(path, "evenodd");
    ctx.strokeStyle = code === selected ? "#ab570c" : "#496f65";
    ctx.lineWidth = code === selected ? 3 : 1;
    ctx.stroke(path);
  }
  el("rows").replaceChildren(...active.sort((a, b) => a.rank - b.rank).map(row => {
    const tr = document.createElement("tr");
    if (row.code === selected) tr.className = "selected";
    const button = document.createElement("button");
    button.textContent = row.district;
    button.addEventListener("click", () => { selected = row.code; render(); });
    tr.insertCell().append(button);
    tr.insertCell().textContent = display(row[key]);
    tr.insertCell().textContent = row.rank;
    return tr;
  }));
  const row = byCode.get(selected);
  el("detail").textContent = row ? [
    `${row.district} · ${row.year}`,
    `新增 ${display(row.added_km2)} km²`,
    `减少 ${display(row.lost_km2)} km²`,
    `邻接新增 ${display(row.adjacent_km2)} km²`,
    `非邻接新增 ${display(row.nonadjacent_km2)} km²`,
    `集约得分 ${display(row.intensive_score)}`,
  ].join(" ｜ ") : "点击地图或选择区县查看分项指标。";
}

canvas.addEventListener("click", event => {
  const rect = canvas.getBoundingClientRect();
  const x = (event.clientX - rect.left) * canvas.width / rect.width;
  const y = (event.clientY - rect.top) * canvas.height / rect.height;
  const hit = paths.find(({ path }) => ctx.isPointInPath(path, x, y, "evenodd"));
  if (hit && records.some(row => row.code === hit.code && (!group.value || row.group === group.value))) {
    selected = hit.code;
    render();
  }
});

async function read(path) {
  const response = await fetch(path);
  if (!response.ok) throw new Error(String(response.status));
  return response.json();
}

Promise.all([read("/dashboard.json"), read("/districts.geojson")]).then(([rows, boundaries]) => {
  records = rows;
  features = boundaries.features;
  buildPaths();
  const years = [...new Set(records.map(row => row.year))].sort((a, b) => b - a);
  years.forEach(value => year.add(new Option(value, value)));
  const exploratory = records.some(row => row.evaluation_basis === "nominal_four_year_exploratory");
  status.textContent = records.some(row => row.data_kind === "demo")
    ? "模拟数据与虚构几何，仅用于系统验证"
    : exploratory ? "四期探索性评分 · 现价指标 · 2010、2015 年经济分项待复核" : "实测数据 · 区级统计";
  [year, group, metric].forEach(control => control.addEventListener("change", () => {
    if (!records.some(row => row.code === selected && (!group.value || row.group === group.value))) selected = null;
    render();
  }));
  render();
}).catch(error => { status.textContent = `数据加载失败（${error.message}）`; });
