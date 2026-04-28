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

