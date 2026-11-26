# 公开替代数据实查

本次先检验真实文件能否下载，再与研究所需的 21 区、2010/2015/2020/2022 四期、三项统计指标以及 WGS84 固定区界对照。已下载的第三方文件未纳入正式面板。

| 数据 | 实查结果 | 可用于 |
|---|---|---|
| 区县名录和编码 | 下载并读取 `areas.json`，重庆研究目录中的 21 个代码与名称均匹配。 | 校对代码、名称和表连接键。 [行政区划数据仓库](https://github.com/modood/Administrative-divisions-of-China) |
| 重庆各区县 2024 年经济数据 | 下载 CSV，内含重庆 38 个区县。研究所需 21 区各有一条，人口、GDP 和第二产业增加值均有正值。文件作者说明其取自《重庆统计年鉴 2025》，本次未能将数值逐项与官方原表交叉核对。 | 真实统计表接入和字段对照，或经复核后作为 2024 年背景资料。2024 年在原定研究期之外。 [GitHub 文件来源及锁定版本](https://github.com/QIAO14/cq-economy-analysis/tree/77d5f6ba8d830b05d7b9538a2277d46905f30a69/data) |
| AreaCity 三级行政区边界 | 下载并解压 2025.251231.260403 版。按六位代码匹配到 19/21 区，缺江北区、渝北区。匹配到的 19 条中有 5 条几何自相交，坐标原为 GCJ‑02。 | 源数据口径与几何质检案例。满足区界完整性、坐标来源和拓扑核验后方可用于区级叠置。 [发布压缩包](https://github.com/xiangyuecn/AreaCity-JsSpider-StatsGov/releases/download/2025.251231.260403/ok_geo.csv.7z) |
| 旧版重庆区县 GeoJSON | 下载到 2015 年提交中的重庆数据。旧版名称与现行目录直接匹配 17/21 区，潼南、璧山、荣昌和铜梁的名称口径有差异。该提交未附坐标参考、来源和许可说明。 | 历史名称排查线索。 [锁定版本的 GeoJSON](https://github.com/longwosion/geojson-map-china/blob/0999e0343308443cf9a2a1490c3eaeea576eb181/geometryCouties/500100.json) |
| geoBoundaries 中国 ADM3 | GitHub 的普通下载返回 Git LFS 指针，文件下载重定向被代理拒绝。 | 备选边界。取得原文件后，仍须核验重庆实际层级、研究单元覆盖、行政变化及授权。 [geoBoundaries 数据目录](https://www.geoboundaries.org/) |
| GISA-new 全球 30 米不透水面 | 公共目录说明提供至 2021 年的首次检出年份。Zenodo 下载入口在本云环境被代理拒绝。 | 如能取得，可据首次出现年份推算 2010、2015、2020 累计新增，作为独立对照。累计产品无法检验用地减少，也缺少 2022。 [目录说明](https://github.com/samapriya/awesome-gee-community-datasets/blob/master/docs/projects/gisa.md) · [数据发布](https://zenodo.org/records/14848113) |
| GHSL 建成表面 | 核验到公开目录，相关栅格下载主机在本云环境被代理拒绝。 | 可作为不同空间分辨率和分类口径下的独立核对。R2023A 的常规历史产品采用五年间隔，建成表面定义与 CLCD 不透水面有差异。 [GHSL 公开目录](https://human-settlement.emergency.copernicus.eu/download.php) |

已下载文件的 SHA‑256

- AreaCity 发布压缩包 `675c3e9b8dec6444994d3ef53259a145304f6a957db8a5e601e55c0b9e61e21a`
- 2024 年经济统计转录 CSV `c634e126d02519b0dd07b86d05a15ab2d8d25705d85fdfa79881a4973e4c02f4`

保留原题时，四期 CLCD 与统计年份完全对应的 84 条真实记录仍待获得。研究区分析还需要一套经法定区划口径和地理坐标验证的 21 区边界。已检验的数据可辅助校对区划代码、验证统计导入和构建后续的数据核验记录。
