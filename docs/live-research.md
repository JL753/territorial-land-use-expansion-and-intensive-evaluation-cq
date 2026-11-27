# 动态科研平台

## 自动检查和版本管理

在 WebGIS、两江立体图、专题大屏、毕设工作台以及桌面和手机页面点击「问山城」，可查询当前数据并展开发布状态。区年问题在提交时获取最新已发布面板，答案带版本、时间范围和数据口径。虎溪建筑、道路、设施的问题读取独立的地图发布。页面采用可选的本机 Ollama 选择证据行，默认统计问答可直接使用。

平台记录源检查状态、发布时间、数据年份和版本号。新数据先经过质检，再重算 TOPSIS、趋势、转换矩阵和时间留出回测。地图和区年研究各自留存快照。来源临时不可用、文件校验失败或区县年份缺失时，已发布成果继续服务。完成初始安装之后，研究数据应通过 `refresh_sources` 更新。

| 数据流 | 更新方式 | 覆盖 |
|---|---|---|
| 虎溪建筑、设施、道路 | 定时访问 OpenStreetMap 官方地图数据接口。记录未变化、发布成功或失败 | 虎溪固定研究框，保留 OSM 数据署名和高度口径 |
| 重庆 21 区区年数据 | 发布批准的本地包，或定时读取受控 HTTPS 清单 | 必须提供可比面板和每区每年来源，自动重算成果 |
| CLCD 年度土地覆盖 | 每 6 小时检查 Zenodo 公开记录版本元数据；大栅格下载与裁剪另行执行 | 公开记录覆盖 1985—2025 产品期，实际可用年份以文件清单为准；当前正式统计仍以已发布区年面板为准 |

新增栅格沿用命名 `CQ_Metro21_LC_YYYY.tif`，与原四期放在同一 rasters 目录，再运行 `tools/build_city_layers.py`。程序发现新栅格年份并生成对应预览。部署时保留生成的 `web/city` 资源和该版本的来源记录。

办公网或云环境访问 OSM 官方接口可能受限。项目可先通过固定出处的开放快照建立版本记录。后续自动检查失败会记入日志，页面显示最后成功观察日。已核验年鉴没有本项目可直接使用的持续推送源，自动区年发布取决于维护人员配置的批准数据清单。初始历史研究并未补造后续观测。

## 启动及定时任务

执行 `docker compose up -d --build` 启动本地 Web 服务与六小时检查任务。两者共享 Docker 命名卷，容器重建后仍可恢复已发布数据。Docker Compose 绑定本机回环地址用于本地运行。公开部署仍按 Django 生产和 HTTPS 代理配置。

使用原有 Python 环境时，先执行迁移。以下任务可交给系统调度器，也可用 `--interval 21600` 独立运行网络检查进程。

```bash
python manage.py migrate
python manage.py import_study --if-empty
python manage.py refresh_sources --osm
python manage.py refresh_sources --bootstrap-osm
python manage.py refresh_sources --bundle /path/to/reviewed-release
python manage.py refresh_sources --restore 1
python manage.py refresh_sources --restore-map 1
```

`--bootstrap-osm` 仅用于首次导入已署名的历史快照。恢复命令的 ID 来自实际发布记录。启用区年网络源时，设置 `CQ_RESEARCH_FEED_URL` 并给检查命令加 `--panel`。默认每次调度应由一个进程执行，临时运行失败时可查看 Django 管理后台中的 RefreshRun。辅助模型设置 `CQ_OLLAMA_MODEL` 后需要同主机有可用 Ollama 服务。

## 数据包和接口

本地包包含 `districts.geojson` 和 `dashboard.json`，字段参照已发布版本。所有记录都需覆盖既有 21 区和原始四期。新增观测年需覆盖全部 21 区。面积、人口、经济量和质量标记均须经过核验。可附 9×9 相邻期地类转移矩阵，系统检查不透水面增减平衡。成果会在最后一个观测阶段上重新进行时间留出检验。质量较低的记录仍应保留标识。

网络源以 HTTPS 提供同样的两个文件，并在同一主机发布 `schema: 1` 清单。每个文件用相对路径和 SHA-256 标识。审核数据后，可用 `python tools/write_release_manifest.py /path/to/reviewed-release` 生成清单。检查程序只取配置源中的文件并拒绝重定向。仓库发布了一个可用于接通流程的基线清单，记录的是既有观测。 [基线发布清单](../results/socioeconomic/four-year-exploratory/release-manifest.json)

```json
{
  "schema": 1,
  "files": {
    "districts.geojson": {"path": "districts.geojson", "sha256": "填入实际文件摘要"},
    "dashboard.json": {"path": "dashboard.json", "sha256": "填入实际文件摘要"}
  }
}
```

| 地址 | 作用 |
|---|---|
| `/api/v1/research/status/` | 源检查状态、当前版本、观察年份和可恢复版本 |
| `/api/v1/research/panel/` | 助手可一次获得同一版本的区年面板 |
| `/api/v1/research/map/` | 返回单次发布的建筑、设施和道路 |
| `/api/v1/analysis/` | 返回与当前研究版本绑定的重算报告 |


CLCD 版本检查只读取 Zenodo API 元数据并写入 `RefreshRun(feed=clcd)`，不在定时 Web/刷新请求中下载数百 MB 的栅格。可手动运行 `python manage.py refresh_sources --clcd`；数据中心 `/data-center.html` 也提供即时版本检查。