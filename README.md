# 重庆市主城都市区建设用地扩张与集约利用评价

《基于多源国土空间数据的重庆市主城都市区建设用地扩张时空格局与集约利用评价系统设计与实现》

研究范围为中心城区 9 区和主城新区 12 区，时点为 2010、2015、2020、2022 年。系统从四期土地覆盖栅格提取区级建设用地面积及变化，关联人口和经济统计，生成熵权 TOPSIS 评价、分组统计和 WebGIS 地图。

- [毕业论文 Word 版](docs/毕业论文.docx) · [可编辑 Markdown 源稿](docs/thesis.md)
- [分析与验证报告](docs/validation.md)
- [数据来源、字段和口径对照](docs/data.md)
- [公开替代数据实查](docs/alternatives.md)
- [四期不透水面扩张实证结果](docs/landcover-results.md)
- [集约利用实证和三份数据交付](docs/socioeconomic-results.md)

## 启动实测 WebGIS

从仓库根目录执行，Python 3.12 即可运行已生成的实测地图和表格。

```bash
python serve.py --results results/socioeconomic/four-year-exploratory
```

浏览器打开 `http://127.0.0.1:8000/`。选择年份、区组和指标，点击区县查看历年明细，或导出当前筛选结果。页面展示四期探索性得分。论文主要采用附件质量等级较高的 2020、2022 年单独拟合结果。

## 运行模拟数据

需要 Python 3.12。以下命令从仓库根目录执行。

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
export MPLCONFIGDIR="$PWD/.cache/matplotlib"
export XDG_CACHE_HOME="$PWD/.cache"
python demo.py
python -m unittest discover -s tests -v
python serve.py --results outputs/demo
```

浏览器打开 `http://127.0.0.1:8000/`。地图和统计值来自合成夹具，页面会标出数据类型。

## 复算实测数据

仓库随附已算好的汇总表和应用数据。若有本项目使用的 `cq_landcover.zip`，解压到 `inputs/` 后可逐像元重现附件口径。从仓库根目录运行：

```bash
python audit_landcover.py inputs/cq_landcover/out --output outputs/landcover
python evaluate_observed.py \
  --socio results/socioeconomic/socio_21district_4year.csv \
  --landcover outputs/landcover \
  --boundaries inputs/cq_landcover/out/boundaries/CQ_Metro21_districts_wgs84.geojson \
  --output outputs/evaluation
```

### 使用其他完整覆盖栅格

先按[数据说明](docs/data.md)准备四期栅格、研究区边界和 84 条区级统计。以下命令中的类别编码 8 应与所获取 CLCD 版本的分类表核对。

```bash
python spatial.py \
  --boundaries inputs/boundaries.geojson \
  --statistics inputs/statistics.csv \
  --raster 2010 inputs/clcd-2010.tif --raster 2015 inputs/clcd-2015.tif \
  --raster 2020 inputs/clcd-2020.tif --raster 2022 inputs/clcd-2022.tif \
  --built-class 8 --data-kind observed --output outputs/observed
python serve.py --results outputs/observed
```

输出包括区级面板 `district_year.csv`、熵权 `weights.csv`、分组汇总 `groups.csv`、分阶段关联 `association.csv`、趋势图 `trends.png`、自动生成的描述报告 `report.md` 和 WebGIS 数据。首期阶段变化字段为空。

## 使用 PostGIS

在 PostgreSQL 16 和 PostGIS 3.5 中新建专用数据库。已有数据库时，先设置标准 PostgreSQL 连接参数 `PGHOST`、`PGPORT`、`PGUSER`、`PGDATABASE`，并通过本机 PostgreSQL 身份验证机制配置密码。以下命令会替换该数据库 `land_use` 模式中的研究数据，用独立数据库分别存放实测和模拟数据。

```bash
(cd results/socioeconomic/four-year-exploratory && psql -f ../../../sql/load.sql)
python serve.py --postgis
```

安装容器版时，可用 `postgis/postgis:16-3.5` 镜像。将输出目录拷入容器后，在容器内该目录执行 `psql -f`，或从宿主机通过已配置的数据库端口执行上述命令。WebGIS 支持年份、区组和指标筛选，可点击地图或使用表格选择区县。
