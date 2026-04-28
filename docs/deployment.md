# 部署说明

本地开发依赖通过 Docker Compose 启动：

```bash
cp .env.example .env
docker compose up -d postgres redis minio
```

应用服务在当前骨架阶段建议分别启动：

- API：`uvicorn app.main:app --reload`
- Worker：`celery -A worker.main.celery_app worker --loglevel=info`
- Web：`npm run dev`

生产部署方案将在数据库模型、异步任务和对象存储接口稳定后补充。

