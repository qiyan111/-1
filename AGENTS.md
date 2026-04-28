你是资深全栈工程师、医疗实验室信息系统架构师、Python 数据分析工程师和前端可视化工程师。请从 0 构建一个“流式细胞术自动化分析与审核平台”。

一、项目背景

系统用于流式细胞术数据分析，目标是替代目前依赖国外软件、流程分散、人工干预多、结果难追溯的工作模式。平台需要覆盖：

1. 数据接收
2. 分析模板管理
3. 分析方案管理
4. 自动化批量分析
5. 自动圈门算法
6. 交互式人工审核
7. 统计计算
8. 结果导出
9. 业务系统集成
10. 用户权限与审计追溯

系统必须满足实验室合规要求，保障数据真实性、完整性、可追溯性，符合 ALCOA+ 思路。

二、总体技术栈

请使用以下架构：

- Monorepo
- 后端：Python FastAPI
- 数据库：PostgreSQL
- ORM：SQLAlchemy
- Migration：Alembic
- 异步任务：Redis + Celery 或 RQ
- 对象存储：MinIO/S3 兼容接口
- 前端：React + TypeScript
- 图形交互：Canvas 或 WebGL 绘制散点/密度图，SVG 叠加可编辑门控图形
- 测试：pytest + 前端测试
- 部署：Docker Compose
- 鉴权：JWT + RBAC
- 审计：append-only audit log

三、系统角色

至少实现以下角色：

1. 管理员
   - 用户管理
   - 角色权限配置
   - 系统配置
   - 查看审计日志
   - 模板与方案全权限

2. 分析员
   - 上传数据
   - 创建和编辑模板
   - 启动自动分析
   - 人工调整门控
   - 保存审核草稿

3. 审核员
   - 查看分析结果
   - 审核确认
   - 退回分析
   - 确认入库

要求：
- 普通用户不能一人完成上传、分析、审核、入库全流程。
- 所有敏感操作必须记录审计日志。

四、核心模块

请按模块设计和实现。

模块 1：数据接收模块

功能要求：
- 支持 FCS、LMD、CSV 文件。
- 支持手动拖拽上传。
- 支持批量上传。
- 支持同一实验号下多管数据。
- 支持上传进度。
- 支持失败文件重试。
- 支持元数据标注：
  - 样本编号
  - 实验号
  - 项目名称
  - 管号
  - 分群组别
  - 实验条件
  - 抗体信息
  - 通道信息
- 支持模板或方案指派。
- 支持自动接收业务系统推送的数据。
- 原始文件保存到对象存储，数据库仅保存路径和元数据。
- 原始数据不可被普通用户删除或覆盖。

模块 2：分析模板管理模块

功能要求：
- 模板列表
- 模板搜索
- 新建模板
- 克隆模板
- 编辑模板
- 删除模板，需权限控制
- 模板版本管理
- 模板版本回滚
- 模板版本差异对比
- 每次保存必须填写更新备注
- 模板包含：
  - 图表配置
  - 管号选择
  - 通道选择
  - 坐标转换
  - 门控定义
  - 父子门关系
  - 逻辑门
  - 统计规则
  - Marker 阈值

图表类型至少支持：
- 散点图
- 密度图
- 彩点图
- 直方图
- 热力图

模块 3：分析方案管理模块

功能要求：
- 一个方案可绑定多个模板。
- 支持一个实验号下多个管。
- 支持一个模板分析多个实验号，即批处理。
- 支持不同检测方案：
  - 管数不同
  - 通道数不同
  - CD Marker 与荧光通道映射不同
- 支持方案版本。
- 支持继承旧方案未修改部分。
- 支持加做管。
- 支持细胞类型标签树。
- 支持 Marker 阈值。
- 支持表达分子百分比、频数、频率、构成比等统计配置。

模块 4：自动化批量分析模块

功能要求：
- 创建分析批次。
- 启动自动分析任务。
- 支持任务状态：
  - 排队
  - 计算中
  - 已完成
  - 失败
  - 暂停
  - 取消
- 支持任务日志。
- 支持失败任务重试。
- 支持完成后进入结果预览。
- 自动分析流程包括：
  - 读取文件
  - 解析事件矩阵
  - 应用补偿矩阵
  - 坐标转换
  - 自动圈门
  - 统计计算
  - 生成图像预览
  - 生成可信度评级
- 可信度评级包括红、黄、绿。

模块 5：门控引擎

请实现独立的 gating engine，不要把门控计算写死在 API 或前端里。

门类型至少支持：
- 矩形门
- 圆形门
- 椭圆门
- 多边形门
- 十字门
- 改进十字门，支持旋转或倾斜
- Linear 门，适用于直方图
- 5 分类门
- 逻辑门

逻辑门至少支持：
- A AND B
- A OR B
- A NOT B
- NOT A
- 嵌套表达式

门控关系要求：
- 支持父子门。
- 子门事件来源于父门。
- 支持拖拽改变门控树层级。
- 修改父门后，子门统计必须重新计算。
- 修改补偿后，相关图和门统计必须重新计算。

每个门控计算应返回：
- gate_id
- gate_name
- event_count
- parent_event_count
- percent_total
- percent_parent
- selected_event_ids 或压缩后的事件集合表示
- statistics

模块 6：自动圈门算法模块

一期先实现传统算法接口，后续可接深度学习模型。

算法接口要求：
- 所有算法实现统一接口。
- 输入 events、channels、parameters。
- 输出 gate definition、confidence score、algorithm metadata。

一期算法至少包括：
- K-Means
- DBSCAN
- Ward 层次聚类
- 一维密度峰谷阈值，FlowDensity 风格
- 自动十字门阈值

要求：
- 自动生成的门可以被人工修改。
- 记录算法名称、版本、参数、运行时间、结果。
- 人工修改后保留算法原始结果和人工最终结果。
- 支持导出人工最终标签，为后续监督学习训练做准备。

模块 7：审核工作台

这是核心前端页面。

页面应包含：
- 样本列表
- 管列表
- 门控树
- 逻辑门树
- 多图展示区域
- 散点图
- 密度图
- 直方图
- 热力图
- 门控图形叠加
- 右侧属性面板
- 统计面板
- Marker 表达面板
- 补偿矩阵调整面板
- 调整日志

交互要求：
- 可新增图。
- 可删除图。
- 可修改图标题。
- 可修改横纵坐标通道。
- 可选择图类型。
- 可新增门。
- 可删除门。
- 可重命名门。
- 可修改门颜色。
- 可隐藏或显示某细胞群颜色。
- 可拖拽门。
- 可调整多边形门的点。
- 可调整矩形门大小。
- 可移动十字门位置。
- 可旋转改进十字门。
- 可在直方图中调整 Linear 门阈值。
- 可高亮门内事件。
- 可放大门内事件。
- 可查看同一管内其他参数表达。
- 可新增逻辑门，如 LYM NOT NK。
- 可拖拽改变父子门关系。
- 修改后实时重新统计。
- 所有修改写入调整记录和审计日志。

模块 8：补偿与坐标转换

功能要求：
- 支持读取补偿矩阵。
- 支持直接编辑补偿矩阵值。
- 支持滑动条快速调整补偿。
- 支持 linear、log、logicle 等坐标转换。
- 修改补偿后重新计算相关数据。
- 补偿修改需要记录审计日志。
- 支持补偿前后效果对比。

模块 9：统计模块

统计要求：
- 门内事件数
- 占全部细胞比例
- 占父细胞群比例
- 占指定细胞群比例
- CD4/CD8 比值
- 多个细胞群求和
- 绝对计数
- Marker 阴阳性
- Marker 高低表达
- 异常细胞群免疫表型文字描述

公式计算要求：
- 支持统计公式配置。
- 支持不同细胞群之间比值。
- 支持多个细胞群求和。
- 支持绝对计数计算。

模块 10：审核确认与入库

功能要求：
- 审核工作台保存草稿。
- 分析员提交审核。
- 审核员查看最终摘要。
- 展示门控调整日志。
- 审核员确认入库。
- 审核员可退回重新调整。
- 入库后结果不可覆盖，只能生成新版本。
- 历史记录支持检索：
  - 日期范围
  - 项目名称
  - 模板
  - 实验号
  - 样本编号
- 历史详情展示：
  - 原始文件
  - 元数据
  - 门控图
  - 统计表
  - 调整日志
  - 审计日志摘要
  - 导出记录

模块 11：结果导出与业务系统集成

导出要求：
- 单张图片导出 PNG、JPEG、PDF、SVG
- 批量图片导出
- Excel 统计表导出
- PDF 报告导出
- JSON 结构化结果
- 原始数据下载
- 调整日志下载
- 审计日志导出

业务系统集成要求：
- 提供 API 自动导入数据。
- 提供 API 查询分析状态。
- 提供 API 获取分析结果。
- 提供 API 获取图片路径。
- 提供 API 回传 KMCS 或既有业务系统。
- 前端支持 iframe 或嵌入模式。
- 系统接口调用也必须写审计日志或集成日志。

模块 12：系统管理与审计

功能要求：
- 系统运行看板
- 历史分析总量
- 当前任务统计
- 存储占用
- 合规性摘要
- 用户管理
- 角色管理
- 权限配置
- 审计日志查询
- 审计日志导出
- 数据备份记录

审计日志要求：
- 不可篡改
- 不可删除
- 记录操作人
- 记录操作时间
- 记录操作类型
- 记录操作内容
- 记录操作结果
- 记录 before 和 after
- 建议使用 hash 链增强防篡改能力

五、数据库表

请至少设计以下表，并使用 Alembic migration：

- users
- roles
- permissions
- user_roles
- role_permissions
- projects
- experiments
- samples
- tubes
- data_files
- channels
- marker_mappings
- compensation_matrices
- analysis_templates
- analysis_template_versions
- template_plots
- template_gates
- template_logic_gates
- template_statistics
- analysis_plans
- analysis_plan_versions
- plan_template_bindings
- cell_label_nodes
- marker_thresholds
- upload_batches
- analysis_batches
- analysis_jobs
- analysis_results
- result_plots
- result_gates
- result_logic_gates
- result_statistics
- result_confidence_scores
- review_sessions
- review_operations
- review_result_versions
- finalized_results
- export_tasks
- integration_push_logs
- audit_logs
- system_settings
- backup_records

六、接口要求

请实现 REST API，并生成 OpenAPI 文档。

基础接口包括：

模板：
- GET /api/templates
- POST /api/templates
- GET /api/templates/{id}
- PUT /api/templates/{id}
- DELETE /api/templates/{id}
- POST /api/templates/{id}/clone
- GET /api/templates/{id}/versions
- POST /api/templates/{id}/rollback
- GET /api/templates/{id}/diff

数据：
- POST /api/uploads
- GET /api/uploads/{batch_id}
- POST /api/uploads/{batch_id}/metadata
- POST /api/uploads/{batch_id}/assign-template
- POST /api/uploads/{batch_id}/start-analysis

分析：
- GET /api/analysis/batches
- GET /api/analysis/batches/{id}
- POST /api/analysis/batches/{id}/pause
- POST /api/analysis/batches/{id}/resume
- POST /api/analysis/batches/{id}/cancel
- POST /api/analysis/batches/{id}/retry

审核：
- GET /api/review/sessions/{id}
- POST /api/review/sessions/{id}/save
- POST /api/review/sessions/{id}/submit
- POST /api/review/sessions/{id}/confirm
- POST /api/review/sessions/{id}/return
- POST /api/review/sessions/{id}/gates
- PUT /api/review/sessions/{id}/gates/{gate_id}
- DELETE /api/review/sessions/{id}/gates/{gate_id}
- POST /api/review/sessions/{id}/recalculate

导出：
- POST /api/exports/images
- POST /api/exports/excel
- POST /api/exports/pdf
- GET /api/exports/{task_id}

系统管理：
- GET /api/admin/dashboard
- GET /api/admin/users
- POST /api/admin/users
- PUT /api/admin/users/{id}
- GET /api/admin/roles
- POST /api/admin/roles
- PUT /api/admin/roles/{id}/permissions
- GET /api/audit-logs
- POST /api/audit-logs/export

七、工程目录建议

请按如下结构初始化：

flow-cytometry-platform/
  apps/
    api/
      app/
        main.py
        core/
        auth/
        audit/
        users/
        projects/
        uploads/
        templates/
        plans/
        analysis/
        gating/
        review/
        exports/
        integrations/
        admin/
        db/
        tests/
      alembic/
      pyproject.toml
    worker/
      worker/
        main.py
        tasks/
        analysis_pipeline.py
        export_pipeline.py
      pyproject.toml
    web/
      src/
        app/
        components/
        pages/
        features/
          auth/
          templates/
          uploads/
          analysis/
          review/
          admin/
        visualization/
          plots/
          gates/
          canvas/
          svg/
        api/
        stores/
        types/
      package.json
  packages/
    shared-schemas/
  docs/
    requirements.md
    architecture.md
    api.md
    gating-engine.md
    deployment.md
  docker-compose.yml
  README.md

八、开发要求

每个任务必须做到：

1. 不破坏已有功能。
2. 后端新增 API 必须有测试。
3. 数据库变更必须有 migration。
4. 关键业务操作必须有权限控制。
5. 敏感操作必须写审计日志。
6. 前端复杂状态要类型安全。
7. 分析算法要可单元测试。
8. 门控几何计算必须独立于前端。
9. 不要把演示数据写死到业务逻辑。
10. README 必须说明如何启动和测试。

九、第一阶段请先完成

请先执行 Task 00 到 Task 04：

Task 00：
- 初始化 monorepo。
- 创建 docker-compose.yml。
- 启动 postgres、redis、minio。
- 创建 api、worker、web 三个应用骨架。

Task 01：
- 实现 FastAPI 项目。
- 实现 /health。
- 配置 SQLAlchemy、Alembic。
- 配置环境变量。

Task 02：
- 实现用户、角色、权限、审计日志的数据库模型。
- 创建 migration。

Task 03：
- 实现 JWT 登录。
- 实现 RBAC 权限中间件。
- 创建默认管理员、分析员、审核员角色。

Task 04：
- 实现审计日志服务。
- 对登录、模板占位接口、文件上传占位接口记录审计日志。
- 实现审计日志查询接口。

完成后请输出：
1. 变更摘要
2. 新增文件列表
3. 如何启动
4. 如何运行测试
5. 下一步建议