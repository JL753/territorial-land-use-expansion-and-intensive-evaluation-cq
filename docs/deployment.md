# 部署与运行

## 本地开发

仓库默认以 Django 开发模式运行，适合本机调试：

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py import_study
python manage.py runserver
```

Windows PowerShell 可将虚拟环境激活命令替换为 `.venv\\Scripts\\Activate.ps1`。

## Docker 生产部署

镜像默认关闭 Django DEBUG。生产启动必须提供独立的随机 `DJANGO_SECRET_KEY`，并配置访问域名和 CSRF 来源。不要将真实密钥写入 Dockerfile、仓库或镜像构建参数。

```bash
docker build -t cq-land-study:latest .
export DJANGO_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
docker run --rm -p 8000:8000 \\
  -e DJANGO_SECRET_KEY="$DJANGO_SECRET_KEY" \\
  -e DJANGO_ALLOWED_HOSTS="study.example.com" \\
  -e CSRF_TRUSTED_ORIGINS="https://study.example.com" \\
  -e DJANGO_TRUST_PROXY=1 \\
  cq-land-study:latest
```

上例假设容器位于 HTTPS 反向代理之后。只有在代理会清理并重写 `X-Forwarded-Proto` 请求头时，才设置 `DJANGO_TRUST_PROXY=1`。如果直接在本机通过 HTTP 调试容器，可显式设置 `DJANGO_DEBUG=1`，但不得将该配置用于公网部署。

容器镜像在构建阶段会使用临时随机密钥执行数据库迁移、研究面板导入和静态资源收集；该密钥不会作为镜像环境变量保留。运行时仍必须提供正式密钥。镜像提供 `/healthz` 就绪检查，只有 21 个区县、84 条区年记录和 2010/2015/2020/2022 四期数据完整时才返回 HTTP 200。

## 关键环境变量

| 变量 | 用途 | 生产要求 |
|---|---|---|
| `DJANGO_DEBUG` | Django 调试模式 | 必须为 `0` |
| `DJANGO_SECRET_KEY` | Django 签名密钥 | 必须使用随机强密钥 |
| `DJANGO_ALLOWED_HOSTS` | 允许访问的主机名，逗号分隔 | 填写实际域名 |
| `CSRF_TRUSTED_ORIGINS` | 可信来源，逗号分隔，包含协议 | 填写实际 HTTPS 来源 |
| `DJANGO_TRUST_PROXY` | 信任反向代理协议头 | 仅可信代理后设为 `1` |
| `CQ_DB_PATH` | SQLite 数据库文件位置 | 持久化部署时挂载可写目录 |
| `CQ_RESULTS` | 使用独立结果快照目录 | 目录必须包含 dashboard.json 和 districts.geojson |
| `CQ_POSTGIS` | 从 PostGIS 快照读取数据 | 设为 `1` 并提供 PostgreSQL 连接环境变量 |
| `CQ_OLLAMA_MODEL` | 启用本机 Ollama 证据选择 | 可选，需保证模型服务可访问 |

## 数据审计与手工验证\n\n在部署前可运行以下命令，对随仓库发布的研究面板、转移矩阵、评价结果和展示边界进行一致性检查。报告会输出 Markdown/JSON，并为每个输入文件记录 SHA-256。\n\n~~~bash\npython audit_study.py --output outputs/data-audit\n~~~\n\n审计状态为 passed_with_warnings 是当前数据预期状态：它表示内部一致性通过，但仍保留早期经济数据等级、名义价格及原始凭证归档等限制。\n\n## 健康检查与手工验证

```bash
curl --fail http://127.0.0.1:8000/healthz
python manage.py check
python manage.py test study
python -m unittest discover -s tests -v
node --test tests/test_client.cjs
```

健康接口只报告研究面板的就绪状态，不替代土地覆盖分类精度、行政边界坐标基准或统计年鉴原始凭证的人工核验。真实研究数据的来源、价格口径、历史行政区划合并和质量标记仍以 [数据目录与口径](data.md)、[实证结果](socioeconomic-results.md) 及 [验证报告](validation.md) 为准。
