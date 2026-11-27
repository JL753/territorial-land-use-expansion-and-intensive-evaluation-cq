# 工程实施与验收清单

## 项目目标

在既有仓库上交付重庆市主城都市区（中心城区 9 区、主城新区 12 区）建设用地扩张与集约利用评价系统。研究时点为 2010、2015、2020、2022 年。系统以 30 m 土地覆盖分类和区级统计面板为输入，输出空间变化、熵权 TOPSIS、WebGIS 查询与可复现研究成果。

## 五阶段实施状态

| 阶段 | 工程交付 | 当前状态 | 尚需外部条件 |
|---|---|---|---|
| 1. 工程基础与部署 | Django 检查、迁移、导入、健康检查、CI、生产配置、Docker 构建 | CI 已覆盖 Python/Django/浏览器测试；Docker 构建新增为必跑 job | 最新 PR 两个 job 全绿；正式域名、TLS、生产密钥、持久化数据库和主机 |
| 2. 核心研究算法 | 栅格面积、地类转移、扩张形态、重心、熵权 TOPSIS、等权/权重敏感性、时间留出回测 | 已有算法实现；新增 TOPSIS 数值性质和异常面板回归测试 | 导师确认指标体系、原始分类版本及独立样本验证 |
| 3. WebGIS 与三端应用 | Web、大屏、移动端、桌面端、地图筛选、图表、矩阵、情景试算、导出、研究助手 | 保留既有功能；新增三端页面、资源白名单和只读接口测试 | 不同浏览器、手机、Windows 实机验收 |
| 4. 数据质量与研究复核 | 21 区 × 4 期面板、63 条变化、5,103 个转移单元、84 条经济面板、GeoJSON 和 SHA-256 审计 | 自动化内部一致性审计已提供；已知质量限制显式保留 | 年鉴原始页、统计修订记录、历史区划合并凭证、CLCD 原始发布件/许可 |
| 5. 成果交付 | 源代码、部署说明、数据字典、论文 Markdown/Word、测试与审计报告生成命令 | 文档、复现入口、CI 报告和客户端构建源码已入库 | 生产部署、Android/Windows/iOS 实机验收、答辩版本签收 |

## 数据与方法边界

1. 研究范围是主城都市区 21 区，不等于重庆全域 38 区县。
2. 遥感建设用地以 CLCD 类别 8 不透水面作为操作化指标，不等同于国土调查法定建设用地或统计建成区面积。
3. 面积核算使用 30 m Albers 等积原生网格和区归属栅格；WGS84 GeoJSON 仅用于地图显示。
4. 2010、2015 年部分 GDP/第二产业值为 B/C 级转录数据。四期评价只能标注为探索性分析；主要比较使用 2020、2022 年 42 条 A 级区年记录。
5. GDP 与第二产业增加值为当年现价时，跨年得分包含价格变化。
6. 区际 Spearman 相关是描述性统计，不支持因果结论。时间留出回测属于同一区域跨期回测，不是跨区外推。
7. 自动审计验证文件内部一致性与输入指纹，不替代遥感分类精度、年鉴原件、边界测绘精度或学术审稿。

## 本地复现与验收命令

~~~bash
python -m pip install -r requirements.txt
python manage.py check
python manage.py migrate --noinput
python manage.py import_study
python manage.py build_analysis --output outputs/analysis
python audit_study.py --output outputs/data-audit
python manage.py test study --verbosity 2
python -m unittest discover -s tests -v
node --test tests/test_client.cjs
~~~

## 交付物索引

- 应用入口：/、/mobile.html、/desktop.html
- 健康检查：/healthz
- 区年数据：/dashboard.json、/districts.geojson、/api/v1/observations/
- 分析 API：/api/v1/analysis/
- 部署：deployment.md
- 数据口径：data.md
- 算法平台：data-platform.md
- 实证结果：landcover-results.md、socioeconomic-results.md
- 论文：thesis.md
- 数据审计：执行 audit_study.py 生成 Markdown 与 JSON 报告
- 客户端构建：clients/android/build.sh、clients/desktop/portable/build.sh、clients/desktop/package.py

## 不能宣称已验收的事项

尚无正式生产主机、域名/TLS 配置和生产数据库凭证；本次未安装/运行 Android SDK、Go Windows cross-build、iOS Safari 或实体手机测试；统计年鉴原始扫描件、CLCD 原始发行文件和行政边界测绘依据未完整归档。工程实现已尽可能自动化，但这些事项需要真实外部资源才能最终签收。
