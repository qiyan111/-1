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

数据库健康检查：

```bash
curl http://127.0.0.1:8000/health/db
```
