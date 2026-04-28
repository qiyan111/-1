# API 服务

FastAPI 后端当前提供基础应用入口、配置管理、CORS、基础异常处理和健康检查。

## 环境变量

常用变量：

- `DATABASE_URL`：完整 PostgreSQL 连接串；为空时由 `POSTGRES_*` 变量拼接。
- `REDIS_URL`：Redis 连接地址。
- `MINIO_ENDPOINT`：MinIO/S3 兼容服务地址。
- `JWT_SECRET`：后续 JWT 签名密钥，本阶段只做配置预留。
- `CORS_ORIGINS`：允许的前端来源，多个值用英文逗号分隔。

## 启动

```bash
cd apps/api
python -m venv .venv
.venv\Scripts\activate
pip install -e .
uvicorn app.main:app --reload
```

健康检查：

```bash
curl http://127.0.0.1:8000/health
```

## 测试

```bash
cd apps/api
pytest
```

## 数据库与 migration

本阶段只接入 SQLAlchemy 和 Alembic，不创建业务表。`DATABASE_URL` 为空时，应用会使用 `POSTGRES_*` 变量拼接 PostgreSQL 连接串。

启动本地 PostgreSQL：

```bash
docker compose up -d postgres
```

查看当前 migration 状态：

```bash
cd apps/api
alembic current
```

后续新增模型后生成 migration：

```bash
cd apps/api
alembic revision --autogenerate -m "create users roles permissions"
alembic upgrade head
```

初始化默认角色与权限：

```bash
cd apps/api
python -m app.users.seed
```

默认管理员账号由以下环境变量控制：

- `DEFAULT_ADMIN_EMAIL`
- `DEFAULT_ADMIN_USERNAME`
- `DEFAULT_ADMIN_PASSWORD`

`python -m app.users.seed` 会创建默认角色、基础权限，并确保默认管理员账号拥有 `admin` 角色。若管理员已存在，脚本不会重置密码，只会确保账号启用且拥有管理员角色。

## 认证接口

登录：

```bash
curl -X POST http://127.0.0.1:8000/api/auth/login ^
  -H "Content-Type: application/json" ^
  -d "{\"username\":\"admin\",\"password\":\"ChangeMe123!\"}"
```

当前用户：

```bash
curl http://127.0.0.1:8000/api/auth/me ^
  -H "Authorization: Bearer <access_token>"
```

审计日志查询，需要当前用户具备 `audit:read` 权限：

```bash
curl http://127.0.0.1:8000/api/audit-logs ^
  -H "Authorization: Bearer <access_token>"
```

## 文件上传与对象存储

对象存储使用 MinIO/S3 兼容接口，相关环境变量：

- `MINIO_ENDPOINT`：MinIO 地址，例如 `http://localhost:9000`
- `MINIO_BUCKET`：原始文件 bucket
- `MINIO_ROOT_USER`：访问密钥
- `MINIO_ROOT_PASSWORD`：访问密钥密码
- `MINIO_SECURE`：是否使用 HTTPS

上传接口需要 `upload:write` 权限，支持 `.fcs`、`.lmd`、`.csv`：

```bash
curl -X POST http://127.0.0.1:8000/api/uploads ^
  -H "Authorization: Bearer <access_token>" ^
  -F "files=@sample.csv"
```

查询上传批次：

```bash
curl http://127.0.0.1:8000/api/uploads/1 ^
  -H "Authorization: Bearer <access_token>"
```

数据库健康检查：

```bash
curl http://127.0.0.1:8000/health/db
```

## 流式数据业务元数据

元数据接口均需要登录。读取接口需要有效 JWT，创建接口需要 `upload:write` 或 `admin:write` 权限，创建成功会写入审计日志。

创建 project：
```bash
curl -X POST http://127.0.0.1:8000/api/projects ^
  -H "Authorization: Bearer <access_token>" ^
  -H "Content-Type: application/json" ^
  -d "{\"code\":\"P001\",\"name\":\"Leukemia Panel\"}"
```

查询 project 列表：
```bash
curl http://127.0.0.1:8000/api/projects ^
  -H "Authorization: Bearer <access_token>"
```

创建 experiment、sample、tube：
```bash
curl -X POST http://127.0.0.1:8000/api/experiments ^
  -H "Authorization: Bearer <access_token>" ^
  -H "Content-Type: application/json" ^
  -d "{\"project_id\":1,\"experiment_no\":\"EXP-001\",\"name\":\"Day 1\"}"

curl -X POST http://127.0.0.1:8000/api/samples ^
  -H "Authorization: Bearer <access_token>" ^
  -H "Content-Type: application/json" ^
  -d "{\"experiment_id\":1,\"sample_no\":\"S-001\"}"

curl -X POST http://127.0.0.1:8000/api/tubes ^
  -H "Authorization: Bearer <access_token>" ^
  -H "Content-Type: application/json" ^
  -d "{\"sample_id\":1,\"tube_no\":\"T-001\",\"data_file_ids\":[1]}"
```

创建 tube 通道与 Marker 映射：
```bash
curl -X POST http://127.0.0.1:8000/api/tubes/1/channels ^
  -H "Authorization: Bearer <access_token>" ^
  -H "Content-Type: application/json" ^
  -d "{\"name\":\"FL1-A\",\"detector\":\"FL1\",\"fluorochrome\":\"FITC\",\"marker\":\"CD3\",\"channel_index\":1}"

curl -X POST http://127.0.0.1:8000/api/tubes/1/marker-mappings ^
  -H "Authorization: Bearer <access_token>" ^
  -H "Content-Type: application/json" ^
  -d "{\"marker\":\"CD3\",\"channel_name\":\"FL1-A\",\"fluorochrome\":\"FITC\"}"
```

本阶段 migration 新增 `projects`、`experiments`、`samples`、`tubes`、`channels`、`marker_mappings`、`compensation_matrices`，并为 `data_files` 增加可空的 `tube_id` 关联字段。

## 分析模板 CRUD

模板读取需要 `template:read` 权限；创建、更新、删除和克隆需要 `template:write` 权限。所有修改操作会写入审计日志。

创建模板：
```bash
curl -X POST http://127.0.0.1:8000/api/templates ^
  -H "Authorization: Bearer <access_token>" ^
  -H "Content-Type: application/json" ^
  -d "{\"name\":\"AML Screening Template\",\"project_code\":\"FLOW-AML\",\"plots\":[{\"title\":\"CD45 SSC\",\"tube_no\":\"T-001\",\"x_channel\":\"CD45\",\"y_channel\":\"SSC-A\",\"plot_type\":\"scatter\"}],\"gates\":[{\"gate_key\":\"lym\",\"name\":\"Lymphocytes\",\"gate_type\":\"polygon\",\"definition\":{\"points\":[[1,1],[2,1],[2,2]]}}],\"logic_gates\":[{\"name\":\"LYM NOT NK\",\"expression\":\"LYM NOT NK\"}],\"statistics\":[{\"name\":\"Percent Parent\",\"rule_type\":\"percent_parent\",\"formula\":\"event_count / parent_event_count\"}]}"
```

查询、更新、删除和克隆：
```bash
curl http://127.0.0.1:8000/api/templates ^
  -H "Authorization: Bearer <access_token>"

curl http://127.0.0.1:8000/api/templates/1 ^
  -H "Authorization: Bearer <access_token>"

curl -X PUT http://127.0.0.1:8000/api/templates/1 ^
  -H "Authorization: Bearer <access_token>" ^
  -H "Content-Type: application/json" ^
  -d "{\"name\":\"Updated Template\",\"project_code\":\"FLOW-AML\",\"plots\":[],\"gates\":[],\"logic_gates\":[],\"statistics\":[]}"

curl -X POST http://127.0.0.1:8000/api/templates/1/clone ^
  -H "Authorization: Bearer <access_token>" ^
  -H "Content-Type: application/json" ^
  -d "{\"name\":\"AML Screening Template Clone\"}"

curl -X DELETE http://127.0.0.1:8000/api/templates/1 ^
  -H "Authorization: Bearer <access_token>"
```

模板创建、更新和克隆需要提供 `change_note`，系统会生成不可覆盖的版本快照。模板版本接口：

```bash
curl http://127.0.0.1:8000/api/templates/1/versions ^
  -H "Authorization: Bearer <access_token>"

curl http://127.0.0.1:8000/api/templates/1/versions/1 ^
  -H "Authorization: Bearer <access_token>"

curl "http://127.0.0.1:8000/api/templates/1/diff?from_version_id=1&to_version_id=2" ^
  -H "Authorization: Bearer <access_token>"

curl -X POST http://127.0.0.1:8000/api/templates/1/rollback ^
  -H "Authorization: Bearer <access_token>" ^
  -H "Content-Type: application/json" ^
  -d "{\"version_id\":1,\"change_note\":\"rollback to validated baseline\"}"
```

rollback 会把模板恢复到指定版本快照，并生成新的当前版本，不覆盖旧版本。diff 当前返回图表、门控、逻辑门、统计规则和通道配置的摘要差异。本阶段 migration 新增 `analysis_templates`、`analysis_template_versions`、`template_plots`、`template_gates`、`template_logic_gates`、`template_statistics`。
