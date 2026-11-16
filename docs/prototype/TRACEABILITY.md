# 原型需求追踪表

## 验收状态更正（2026-11-16）

下表早期“已完成”只反映接口或入口存在，不代表原型视觉和完整交互通过验收。
此前将其作为原型对齐完成依据不充分；最终验收应以逐项交互和同视口截图对照为准。

本次已实现：新建实验页独立标题栏、横向方式卡片、场景/算法/摘要三列布局，
1340px 和 900px 响应式降列；启用开关接入算法配置；单次实验固定一次；错误禁用运行。

仍待实现或验证：完整 Schema 场景字段、字段旁扫描绑定、指标选择和门限、
算法能力与训练范围警告、真实空间谱、按信源分组的分布、场景集评测、插件发现和模型包。
本次不能据此宣称全部原型对齐完成。

本文把 `docs/prototype/index.html` 和 `docs/05_产品原型.md` 中的页面要求映射到正式实现。状态含义：`已完成`、`本阶段修复`、`部分完成`、`待实现`。

| 原型区域 / 条目 | 正式组件 | 后端 API / 数据 | 测试与验收 | 状态 |
|---|---|---|---|---|
| 全局：工作目录切换器 | `Layout.tsx` | `GET/POST/PUT /api/workspaces`、`GET/PUT /api/workspaces/current` | 工作目录切换集成测试、浏览器切换验收 | 已完成 |
| 全局：分组导航、当前任务 | `Layout.tsx` | `GET /api/tasks/{id}`、SSE | 前端路由测试、浏览器验收 | 本阶段修复 |
| 新建实验：实验名称和顶部操作 | `ExperimentConfig.tsx` | `GET /api/schema/experiment`、模板 API | Schema API、提交配置测试 | 本阶段修复 |
| 新建实验：单次/蒙特卡洛/扫描卡片 | `ExperimentConfig.tsx` | `ExperimentConfig.type`、`sweep` | 配置类型测试 | 已完成 |
| 新建实验：Schema 驱动场景字段 | `SchemaForm.tsx`、`ImpairmentConfig.tsx` | `GET /api/schema/experiment` | Schema 渲染、完整配置提交测试 | 本阶段修复 |
| 新建实验：算法卡片折叠、复制、删除 | `AlgorithmCard.tsx` | `GET /api/algorithms` | 算法列表 API、浏览器验收 | 已完成 |
| 新建实验：右侧预览与配置摘要 | `ScenePreview.tsx`、`ConfigSummary.tsx` | 实验草稿状态 | 前端组件测试、浏览器验收 | 本阶段修复 |
| 新建实验：底部运行栏和预计工作量 | `ExperimentConfig.tsx` | 配置校验、任务提交 | 提交前校验测试 | 已完成 |
| 运行与结果：状态、进度、SSE | `ExperimentRun.tsx` | `GET /api/experiments/tasks/{id}`、SSE | Web Service/Runner 集成测试 | 已完成 |
| 运行与结果：扫描曲线、图例、导出图 | `ResultCharts.tsx` | `/charts`、`/export/{format}` | 图表接口、导出测试 | 已完成 |
| 运行与结果：单次空间谱、蒙特卡洛分布 | `ResultCharts.tsx` | `summary.json`、`results.npz` | 结果模型测试、浏览器验收 | 已完成 |
| 历史：筛选、选择、复制、重跑、删除 | `History.tsx` | 任务索引、copy/rerun/delete API | Web Service 集成测试 | 已完成 |
| 对比：最多 4 个同变量扫描实验 | `Compare.tsx` | `/charts`、任务配置 | 选择约束测试、浏览器验收 | 已完成 |
| 对比：不同设置表和双重图例 | `Compare.tsx` | 任务 `config` | 设置差异表、对比数据测试 | 已完成 |
| 算法库：刷新、失败插件、模型包 | `Algorithms.tsx` | `/algorithms/refresh`、`/algorithms/sources` | 算法刷新集成测试、刷新按钮验收 | 已完成（模型包保留扩展位） |
| 模板：类型筛选、内置/工作目录层级 | `Templates.tsx` | 模板 CRUD API | 模板 API 集成测试 | 已完成 |
| 排行榜：场景集和补跑 | `Leaderboard.tsx` | `/leaderboard/scenarios`、`/leaderboard` | 排行榜集成测试、页面验收 | 已完成（补跑沿用历史实验重跑） |
| 设置：工作目录表、外部算法来源、环境信息 | `Settings.tsx` | settings/workspaces/environment API | 设置与工作目录集成测试 | 已完成 |

## 本阶段实施范围

本阶段先完成两项：

1. 全局布局：工作目录入口、分组导航、当前任务入口、运行/对比页面不作为主导航项。
2. 新建实验页：原型规定的顶部操作、实验方式卡片、三栏结构、Schema 配置入口、右侧预览摘要和底部运行操作栏。

每完成一项，必须同时更新本表的状态，并补充至少一个 API、组件或浏览器验收证据。


## 2026-11-16 配置专项状态（覆盖上表对应项）

| 需求 | 组件 | API / 核心 | 验收证据 | 状态 |
|---|---|---|---|---|
| 完整插件 Schema 字段 | ConfigFields、ExperimentConfig | schema/experiment、真实 Params | test_schema_contains_all_plugin_fields；浏览器误差字段 | 已实现 |
| 数值字段旁扫描与范围输入 | ConfigFields | expand_point、build_scene | 快拍/算法参数扫描测试；浏览器 SNR 和误差扫描 | 已实现 |
| 指标选择与成功门限 | ExperimentConfig | MetricsConfig、compute_metrics、charts | 门限统计测试；浏览器指标切换 | 已实现 |
| 同一配置运行/保存/导出 | ExperimentConfig.build | 模板 API、run API | 单一配置构建路径；运行任务 21aac325 | 已实现 |
| 中文摘要及紧凑布局 | ExperimentConfig、index.css | Schema 标签 | HTTP 原型与实际截图对照 | 已复验 |

此前表中的“已完成”不应解释为全产品逐像素验收通过。真实空间谱、外部模型包、场景集评测等仍须按独立范围验收；详见本轮测试报告。
