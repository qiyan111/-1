# 流式细胞术自动化分析与审核平台实施计划

## 摘要

当前仓库以 `D:\流式自动化分析平台` 作为 monorepo 根目录，不再嵌套二级项目目录。第一阶段先完成工程骨架、基础服务编排、后端健康检查、worker 占位、前端 Vite 骨架和文档体系，为 Task 00 到 Task 04 的正式实现打基础。

默认技术决策：

- 后端使用 FastAPI、SQLAlchemy、Alembic、Pydantic Settings 和 pytest。
- 异步任务使用 Redis + Celery。
- 对象存储使用 MinIO 的 S3 兼容接口。
- 前端使用 React + TypeScript + Vite。
- 门控计算作为独立后端 engine，不写死在 API 或前端中。
- 审计日志采用 append-only 设计，并在后续实现 hash 链增强防篡改能力。

## 阶段计划

### Phase 0：monorepo 与基础骨架

交付物：

- 根目录 `docker-compose.yml`，启动 PostgreSQL、Redis、MinIO。
- `apps/api`、`apps/worker`、`apps/web` 三个应用骨架。
- `packages/shared-schemas` 共享 schema 包占位。
- `docs` 文档目录与 `README.md`。

验收标准：

- `docker compose config` 通过。
- 后端、worker、前端目录结构完整。
- README 包含启动和测试说明。

### Phase 1：FastAPI、配置、数据库入口

交付物：

- FastAPI 应用工厂和 `/health` 接口。
- Pydantic Settings 读取环境变量。
- SQLAlchemy engine/session/base。
- Alembic 配置和版本目录。
- `/health` 测试。

验收标准：

- `python -m compileall apps/api/app apps/worker/worker` 通过。
- `cd apps/api && pytest` 通过。
- OpenAPI 文档可由 FastAPI 自动生成。

### Phase 2：用户、角色、权限、审计模型

交付物：

- `users`、`roles`、`permissions`、`user_roles`、`role_permissions`、`audit_logs` 模型。
- Alembic migration。
- 模型约束：唯一用户名、唯一角色编码、唯一权限编码、审计日志不提供业务删除路径。

验收标准：

- migration 可在空 PostgreSQL 数据库上执行。
- 模型测试覆盖基础关系和约束。

### Phase 3：JWT 登录与 RBAC

交付物：

- 登录接口、JWT access token、密码哈希。
- 当前用户解析依赖。
- RBAC 权限校验依赖或中间件。
- 默认管理员、分析员、审核员角色和基础权限种子数据。

验收标准：

- 登录成功和失败路径有测试。
- 未授权、无权限、权限通过三类路径有测试。
- 普通用户不能被授予单人完成上传、分析、审核、入库全流程的组合权限。

### Phase 4：审计日志服务与占位接口审计

交付物：

- 审计日志服务，记录 actor、action、resource、before、after、result、request_id、hash 链字段。
- 登录、模板占位接口、文件上传占位接口写审计日志。
- `GET /api/audit-logs` 和 `POST /api/audit-logs/export` 占位接口。

验收标准：

- 敏感操作成功和失败均记录审计。
- 审计查询支持基础分页和过滤。
- 测试验证审计日志 append-only 行为。

### Phase 5+：业务模块演进

后续按依赖顺序推进：

- 上传模块：批量上传、元数据、MinIO 路径、失败重试、模板或方案指派。
- 模板与方案：版本管理、差异对比、门控定义、统计规则、Marker 阈值。
- 分析批次：Celery 任务状态、日志、重试、可信度评级。
- 门控引擎：矩形、圆形、椭圆、多边形、十字、改进十字、Linear、5 分类、逻辑门。
- 自动圈门算法：K-Means、DBSCAN、Ward、FlowDensity 风格阈值、自动十字门阈值。
- 审核工作台：Canvas/WebGL 绘图，SVG 叠加门控图形，实时重算和调整日志。
- 导出与集成：图片、Excel、PDF、JSON、业务系统推送和回传。
- 系统管理：用户、角色、权限、审计查询、备份记录、运行看板。

## 合规原则

- 原始数据进入对象存储后不可被普通用户删除或覆盖。
- 入库结果不可覆盖，只能生成新版本。
- 所有敏感操作必须写入审计日志。
- 审计日志只追加，不提供业务删除能力。
- 审计日志记录 before 和 after，并保留操作结果。
- 通过职责分离保证普通用户不能一人完成上传、分析、审核、入库全流程。

## 测试策略

- 后端新增 API 必须有 pytest 测试。
- 数据库变更必须有 Alembic migration，并至少覆盖空库升级。
- 权限相关代码覆盖未登录、无权限、有权限三类场景。
- 审计相关代码覆盖成功、失败和异常路径。
- 门控几何计算作为纯函数或独立服务测试，不依赖前端。
- 前端复杂状态使用 TypeScript 类型约束，并在核心交互稳定后补充组件测试。

## 当前骨架验收命令

```bash
docker compose config
python -m compileall apps/api/app apps/worker/worker
cd apps/api && pytest
cd ../web && npm install && npm run build
```

