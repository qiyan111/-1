# 流式细胞术自动化分析与审核平台

这是流式细胞术自动化分析与审核平台的 monorepo 骨架。当前阶段只包含可扩展的工程结构、基础服务编排、后端健康检查、worker 占位任务、前端 Vite 骨架和实施计划文档。

## 目录结构

```text
apps/
  api/       FastAPI 后端
  worker/    Celery 异步任务应用
  web/       React + TypeScript 前端
packages/
  shared-schemas/  前后端共享类型占位
docs/        架构、API、门控引擎、部署和实施计划
```

## 启动基础依赖

```bash
cp .env.example .env
docker compose up -d postgres redis minio
```

MinIO 控制台默认地址为 `http://localhost:9001`，本地默认账号密码见 `.env.example`。

## 启动后端

```bash
cd apps/api
python -m venv .venv
.venv\\Scripts\\activate
pip install -e .
uvicorn app.main:app --reload
```

健康检查：

```bash
curl http://localhost:8000/health
```

## 启动 worker

```bash
cd apps/worker
python -m venv .venv
.venv\\Scripts\\activate
pip install -e .
celery -A worker.main.celery_app worker --loglevel=info
```

## 启动前端

```bash
cd apps/web
npm install
npm run dev
```

## 运行测试和校验

```bash
python -m compileall apps/api/app apps/worker/worker
cd apps/api && pytest
cd ../web && npm install && npm run build
```

## 下一步

按照 [docs/implementation-plan.md](docs/implementation-plan.md) 继续实现 Task 01 到 Task 04：数据库模型、Alembic migration、JWT、RBAC、默认角色、审计日志服务和审计查询接口。

