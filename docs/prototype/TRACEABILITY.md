> 2026-11-17：本轮最新状态以 [P0/P1 逐项追踪表](P0_P1_TRACEABILITY.md) 和 [验收报告](../milestones/P0_P1_ACCEPTANCE_2026_11_17.md) 为准；下文保留历史记录。

> 2026-11-16：当前重新验收证据见 [M1–M5 重新验收记录](../milestones/M1_M5_ACCEPTANCE_AUDIT.md)。新增真实谱、逐源误差分布、插件发现、脚本与历史恢复测试；下表旧有“已完成”仍须逐项浏览器复核，不代表完整验收。

# 原型需求追踪表

## 当前增量验收（2026-11-16，覆盖旧表同名项）

| 原型需求 | 组件 | API / 核心 | 测试证据 | 当前结论 |
|---|---|---|---|---|
| 执行选项真实生效 | ConfigFields | source_count / batch / parallel | test_execution_options、test_parallel_runner | 自动化通过，界面待复验 |
| 指标重算 | RecomputeMetrics、ResultCharts | POST tasks/{id}/recompute | test_metric_recompute_api_preserves_raw | 自动化通过，界面待复验 |
| 备注、标签、收藏、改名 | ExperimentNotes、History | GET/PUT tasks/{id}/notes | test_notes_do_not_mutate_experiment_config | 自动化通过，界面待复验 |
| 脚本结果自动进入历史 | History | SQLite 索引、文件增量扫描 | test_sqlite_index_rebuild_and_live_script_discovery | 自动化通过 |
| 排队及中断恢复 | ExperimentRun | FIFO、heartbeat、finalize | test_task_queue_runs_one_at_a_time、test_restart_cancels_queue_and_detects_interrupted | 队列与判定通过，整理入口待复验 |
| 原型场景预览及紧凑参数行 | ScenePreview、ConfigFields、index.css | schema/experiment | 构建与类型检查 | 修改已实现，视觉待验收 |
| 后端配置类型一致 | generated.ts | OpenAPI ExperimentConfig / ExperimentNotes | generate_api_types.py --check | 已生成；其他响应类型待迁移 |

此表不把“自动化通过”记为“原型视觉通过”。M6 模型闭环、M7 排行榜在本轮 M1–M5 范围之外。

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


## 2026-11-16 持续验收状态（优先于早期“已完成”）

| 原型需求 | 组件 | API / 核心 | 自动化证据 | 视觉状态 |
|---|---|---|---|---|
| Schema 指标参数与卡片警告 | ConfigFields / ExperimentConfig | schema / experiments/validate / 四类插件 | remaining_contract、plugins_acceptance、web_service | 待本轮逐项复验 |
| 当前图表与指定指标导出 | ResultCharts | export?chart=&metric= / export.service | export_truth、selected_chart_export | 待本轮复验 |
| 中断实验整理 | ExperimentRun | finalize / points 合并 | checkpoint_point_files_and_finalize | 待本轮复验 |
| 工作目录共享脚本结果 | Layout / Settings | Workspace / workspaces/current | web_workspace_uses_same_layout_as_script | 待本轮复验 |
| 类型与模板真实配置 | Templates / API client | OpenAPI 生成 | 类型检查、模板 CRUD / 越界保护 | 待本轮复验 |

早期“排行榜已完成”“模型包完整”的表述不成立：这两项分别归属 M7、M6。本次只验收 M1–M5，不能以占位或历史重跑代替其正式功能。

## 2026-11-16 M6–M7 实现及验收追踪

| 原型需求 | 组件 / 入口 | API / 核心 | 验收证据 | 状态 |
|---|---|---|---|---|
| 模型包检查、导入与训练元信息 | Algorithms / ModelsPanel | models/inspect、models/import / core.models | test_models；真实 CNN 包 HTTP 检查导入 | 功能通过，视觉待验 |
| 学习算法选择模型 | ConfigFields / ModelSelector | Params 的 x-widget=model / ModelAlgorithm | test_learning_workflow；实际任务 e77c2313 | 功能通过，视觉待验 |
| 超训练范围提示与复现信息 | ExperimentConfig / 实验结果 | validate、模型 SHA256 与 provenance | SNR=30 dB 警告及双算法零异常 | 功能通过，视觉待验 |
| 云端数据生成与训练 | dataset CLI / 独立课题脚本 | datasets / TorchDataset | Linux Python 3.10 CI、在线离线一致、spawn DataLoader | 自动化通过；未操作真实 AutoDL |
| 标准场景集、版本选择 | Leaderboard | benchmarks/suites / BenchmarkSuite | 不可变版本、内容哈希、版本隔离 | 通用功能通过；正式 1.0 待故障数确认 |
| 运行与任务关联 | Leaderboard / ExperimentRun | benchmarks/runs / 普通任务队列 | 实际 8 场景每点 500 次完成 | 功能通过，视觉待验 |
| 指定点排名与结果跳转 | Leaderboard | leaderboard / summary 指定 metric_values | 两算法 16 个结果链接、无缺失项、配置篡改排除测试 | 功能通过，视觉待验 |
| 最新/历史记录、缺失补跑 | Leaderboard | revision / scenarios 选择 | test_benchmark_run_version_isolation_and_missing_scenes | 自动化通过，视觉待验 |

完整验收状态以 `docs/milestones/M6.md`、`M7.md` 为准；上述功能通过不代表逐项视觉验收完成。

2026-11-17 更新：官方内置浏览器已实际复验算法库表格、搜索/详情、模型检查弹窗、排行榜切换/单位/排名与结果跳转，并修复重启进度显示。上述相关项的“视觉待验”更新为“主要路径已复验”；范围和截图见 `docs/milestones/VISUAL_ACCEPTANCE_2026_11_17.md`，其他条目不据此自动通过。


## 2026-11-17 全产品浏览器复验（覆盖早期状态）

| 原型需求 | 组件 | API / 核心 | 验收证据 | 当前状态 |
|---|---|---|---|---|
| 布局、Schema 配置、场景预览 | Layout / ExperimentConfig / ScenePreview | schema/preview / exploration | 1440 与 1024 视口；随机角度/故障预览回归 | 已复验并修复 |
| 单次谱及独立估计标记 | ResultCharts / ResultTable | charts、details / figures | 7ea7ed87；线性谱/无谱回归 | 已复验并修复 |
| 蒙特卡洛分布、指标及重算 | ResultCharts / RecomputeMetrics | figures/details、recompute | 184a1dcb；门限重算 30% / 5% | 已复验并修复 |
| 扫描点联动与当前图导出 | ResultCharts / ResultTable | export.service | 曲线点选、HTML 下载；导出自动化 | 已复验并修复 |
| 运行、失败、取消、部分结果 | ExperimentRun | runner.job / storage.reader | db2cff3e 复现；6bb3fd20 最终 9984 次；并发文件替换回归 | 已复验并修复 |
| 中断整理与重启进度 | ExperimentRun | finalize / tasks | 状态夹具 40/80 整理后刷新；自动化恢复进度 | 已复验并修复 |
| 搜索筛选、收藏及比较准入 | History / experimentViews | tasks / notes | 非扫描选择禁用；同变量两任务可比较；前端测试 | 已复验并修复 |
| 差异表、语义对比及导出 | Compare | compare/export / figures.compare | 快拍扫描 500/2 次、点选 x=500、HTML 下载 | 已复验并修复 |
| 模板类型、保存、回收 | Templates / ExperimentConfig | templates / 当前工作目录 | UI 保存与回收临时模板、空搜索、保留算法；API 回归 | 已复验并修复 |
| 算法详情及模型错误反馈 | Algorithms / ModelsPanel | algorithms / models | 中文字段、加入新实验、无效路径弹窗；模型回归 | 已复验并修复 |
| 工作目录及真实环境 | Settings | workspaces、settings/environment | 表格/复制环境、登记 API、隔离探测 | 已复验并修复 |
| 排名、历史版本、运行选择 | Leaderboard | benchmarks | 500 次验收版本、历史记录、空算法选择禁用、前轮结果跳转 | 页面复验完成；正式九场景仍待确认 |

完整范围、真实任务 ID、缺陷复现、最终测试与边界见 [全产品视觉验收报告](../milestones/FULL_VISUAL_ACCEPTANCE_2026_11_17.md)。这次覆盖全部产品页面，不将 CUDA、AutoDL 或正式场景集待定设计自动标记为通过。


## 2026-11-17 M7 九场景正式验收

故障数及参考阵元规则已获需求方批准，覆盖上文“正式九场景待确认”状态。正式完整评测 `20261117-130215_bench_20e0476d`：9 场景、53 点、每点 500 次、算法异常 0；哈希和干净 commit 逐项核验。新增故障列排名、结果跳转、第三点数值、历史版本及单场景补跑均经官方内置浏览器验收。实际补跑记录 `20261117-131550_bench_85c2d302`。排队场景不再显示补跑按钮；侧栏优先展示运行任务。回归与失败记录见 [M7 报告](../milestones/M7.md)。M6 的真实 AutoDL 环境不据此标记为通过。

GPU 设备显示与模型链路补验：独立 CUDA 环境下设置页真实显示 RTX 5060 / CUDA 13.0，HTTP 模型任务 ae143ed8 完成、异常 0；GPU 全套 170 项通过。详情见 [GPU 环境报告](../milestones/GPU_ACCEPTANCE_ENVIRONMENT.md)。
