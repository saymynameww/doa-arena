# 原型需求追踪表

本文把 `docs/prototype/index.html` 和 `docs/05_产品原型.md` 中的页面要求映射到正式实现。状态含义：`已完成`、`本阶段修复`、`部分完成`、`待实现`。

| 原型区域 / 条目 | 正式组件 | 后端 API / 数据 | 测试与验收 | 状态 |
|---|---|---|---|---|
| 全局：工作目录切换器 | `Layout.tsx` | `GET/POST /api/workspaces` | API 设置测试、浏览器切换验收 | 部分完成 |
| 全局：分组导航、当前任务 | `Layout.tsx` | `GET /api/tasks/{id}`、SSE | 前端路由测试、浏览器验收 | 本阶段修复 |
| 新建实验：实验名称和顶部操作 | `ExperimentConfig.tsx` | `GET /api/schema/experiment` | Schema API、提交配置测试 | 本阶段修复 |
| 新建实验：单次/蒙特卡洛/扫描卡片 | `ExperimentConfig.tsx` | `ExperimentConfig.type`、`sweep` | 配置类型测试 | 部分完成 |
| 新建实验：Schema 驱动场景字段 | `SchemaForm.tsx`、`ImpairmentConfig.tsx` | `GET /api/schema/experiment` | Schema 渲染、完整配置提交测试 | 本阶段修复 |
| 新建实验：算法卡片折叠、复制、删除 | `AlgorithmCard.tsx` | `GET /api/algorithms` | 算法列表 API、浏览器验收 | 部分完成 |
| 新建实验：右侧预览与配置摘要 | `ScenePreview.tsx`、`ConfigSummary.tsx` | 实验草稿状态 | 前端组件测试、浏览器验收 | 部分完成 |
| 新建实验：底部运行栏和预计工作量 | `ExperimentConfig.tsx` | 配置校验、任务提交 | 提交前校验测试 | 待实现 |
| 运行与结果：状态、进度、SSE | `ExperimentRun.tsx` | `GET /api/experiments/tasks/{id}`、SSE | Web Service/Runner 集成测试 | 已完成 |
| 运行与结果：扫描曲线、图例、导出图 | `ResultCharts.tsx` | `/charts`、`/export/{format}` | 图表接口、导出测试 | 部分完成 |
| 运行与结果：单次空间谱、蒙特卡洛分布 | `ResultCharts.tsx` | `summary.json`、`results.npz` | 结果模型测试、浏览器验收 | 待实现 |
| 历史：筛选、选择、复制、重跑、删除 | `History.tsx` | 任务索引、copy/rerun/delete API | Web Service 集成测试 | 部分完成 |
| 对比：最多 4 个同变量扫描实验 | `Compare.tsx` | `/charts`、任务配置 | 选择约束测试、浏览器验收 | 部分完成 |
| 对比：不同设置表和双重图例 | `Compare.tsx` | 任务 `config` | 对比数据测试 | 待实现 |
| 算法库：刷新、失败插件、模型包 | `Algorithms.tsx` | 算法发现/模型包 API | 算法发现测试 | 待实现 |
| 模板：类型筛选、内置/工作目录层级 | `Templates.tsx` | 模板 CRUD API | 模板 API 集成测试 | 部分完成 |
| 排行榜：场景集和补跑 | `Leaderboard.tsx`（待建） | 场景集/排行榜 API（待建） | 排行榜集成测试 | 待实现 |
| 设置：工作目录表、外部算法来源、环境信息 | `Settings.tsx` | settings/workspaces/environment API | 设置集成测试 | 部分完成 |

## 本阶段实施范围

本阶段先完成两项：

1. 全局布局：工作目录入口、分组导航、当前任务入口、运行/对比页面不作为主导航项。
2. 新建实验页：原型规定的顶部操作、实验方式卡片、三栏结构、Schema 配置入口、右侧预览摘要和底部运行操作栏。

每完成一项，必须同时更新本表的状态，并补充至少一个 API、组件或浏览器验收证据。
