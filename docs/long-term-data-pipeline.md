# 全域年度数据与三维场景实施说明

## 年度 CLCD 处理

先抽样试运行：

    python tools/build_clcd_district_series.py --years 2010,2015,2020,2025

完整处理：

    python tools/build_clcd_district_series.py

脚本从 Zenodo 元数据读取 CLCD 年度 COG 文件清单，通过 GDAL /vsicurl/ HTTP Range 读取每个区县自己的栅格窗口，不下载整幅中国栅格。默认处理当前记录中全部可用年度文件。输出 state/clcd-district-series.json，独立于原区年社会经济面板。

每个区县、每个产品年份输出 CLCD class 8（不透水面）面积、其他地类面积、有效/缺测面积、相邻可用年份转移矩阵、新增/减少/净变化面积、源文件 checksum 和处理元数据。缺失年份不插值；跨期扩张强度按实际间隔年数折算。

## 研究口径

- CLCD 是年度 Landsat 土地覆盖产品，不是实时卫星流。
- CLCD class 8 是建设用地扩张的遥感操作化代理，不等同于法定建设用地。
- 人口、GDP、产业数据继续单独存储。没有官方证据的年份不推算、不填补。
- 仅有遥感数据的年份不计算集约利用得分。
- 边界版本、CLCD 记录 ID、文件 checksum、处理时间、CRS 和像元面积随结果保存。

## 多源数据

| 数据 | 接入方式 | 时效 |
|---|---|---|
| CLCD | Zenodo 元数据 + COG Range 读取 | 年度产品发布后同步 |
| OSM 建筑/道路/POI | Geofabrik 重庆 PBF 区域快照 | 可按日/周同步；覆盖度因区而异 |
| 地形 DEM | AWS Terrain Tiles 在线地形瓦片；Copernicus DEM 可下载 | 静态产品，非实时 |
| 区县统计 | 重庆统计年鉴、统计公报 | 官方发布后更新 |

OSM 派生数据须按 ODbL 1.0 署名并遵守共享条款。OSM 缺少建筑记录不代表地面无建筑。

## 全域三维

/ district.html?code=500105 是可切换的 21 区县三维地形场景。DEM 地形来自在线 Terrarium 高程瓦片，区县边界来自仓库 GeoJSON。CLCD 序列生成后，区县页面和 Cesium 大屏会将遥感年度指标加入年份选择器。指标拉伸仅用于专题表达，不代表真实建筑高度。真实建筑模型需建筑轮廓与可信高度数据；现有虎溪建筑模型不能外推至其他区县。

## AI 助手

全站悬浮助手提供当前已发布数据的查询和证据解释。云端大模型需部署者配置兼容 OpenAI Chat Completions 的服务地址、模型和 API Key；未配置时保留本机 Ollama 或规则化研究查询。不得把规则查询称为模型推理。

## 部署

容器应持久化 /app/state 卷。本地运行确保 state/ 可写。完整年度处理可能需要较长网络读取和处理时间，先执行小批量年份检查 CRS、边界和有效像元比例。派生数据不会提交进 Git，避免将大型数据文件混入源码。


## 21 区县 OSM 三维要素

运行 `python tools/build_chongqing_osm_layers.py` 自动下载 Geofabrik 重庆区域 PBF，并按 21 区县边界切分建筑轮廓、道路和 POI 到 `state/osm-21/`。各区县页面按当前区县代码按需加载对应 GeoJSON。建筑高度优先采用 OSM `height`，其次使用 `building:levels × 3 m` 估算，仍缺失时使用 6 m 概化高度；属性 `height_source` 会标明来源。该高度仅用于可视化，不是实测高度。OSM 数据遵守 ODbL 1.0，页面需保留 OpenStreetMap 署名。




## Docker 一次性数据构建

先构建应用镜像，再执行 `docker compose --profile data-build run --rm spatial-data-build`。该一次性服务依次生成 CLCD 年度区县序列和重庆 21 区县 OSM 建筑/道路/POI 图层，输出保存在持久化的 `study-state` 卷中。首次处理建议预估网络和磁盘资源；若只想快速验收，可先在本机直接运行 CLCD 脚本的 `--years 2010,2015,2020,2025` 抽样参数，再执行全年度。
