# 架构说明

系统采用 monorepo：

- `apps/api`：FastAPI REST API，负责认证、权限、审计、业务接口和 OpenAPI 文档。
- `apps/worker`：Celery worker，负责自动分析、导出等异步任务。
- `apps/web`：React + TypeScript 前端，负责上传、模板管理、审核工作台和系统管理。
- `packages/shared-schemas`：共享类型和 schema 的占位包。

基础设施：

- PostgreSQL 保存业务元数据、权限、审计和分析结果。
- Redis 作为 Celery broker/result backend。
- MinIO 保存原始文件、预览图、导出文件等对象。

