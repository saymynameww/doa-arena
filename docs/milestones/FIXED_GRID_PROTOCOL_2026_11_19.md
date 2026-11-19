# 固定网格公平对比协议实施报告（2026-11-19）

## 1. 完成内容

需求方已批准本次算法默认值、配置格式和设计文档修订。

- CBF、MVDR、MUSIC 新实验默认使用实验级 `search_grid`（−90° 到 90°，0.1°），固定格点寻峰，不自动细化或随 SNR 调整。
- 算法卡片提供显式 `none`、`parabolic`、`local_dense` 选择；局部加密终止步长单独记录。独立网格也作为显式对比变体。Root-MUSIC、TLS-ESPRIT 等无网格算法保持原生求解。
- 统一网格及策略由后端 Schema 驱动；保存、导出、执行记录有效参数，算法/API 版本升至 1.1.0。排行榜记录规范化的参数，避免新旧默认策略混为同一参数组合。
- 实验配置格式升至 v2。读取 v1 时保留原独立网格、旧 `arange` 舍入及 `refine` 含义；省略 `refine` 的旧实验仍为抛物线插值。旧用户模板未写版本时按 v1 处理。历史结果与文件不改写，新保存或复制配置显式记录兼容参数。
- 显式旧 `refine=true/false` 输入仍可读取，冲突参数报错；新建无版本 Python 配置采用 v2 默认值。仅凭缺省字典无法辨识其创建年代，重放旧脚本应声明 `schema_version=1`。
- 00–05 设计文档、HTTP 原型及需求追踪表已同步。信号模型和随机数派生未改变，GENERATOR_VERSION 保持 3。

## 2. 怎么验收

```powershell
$env:MKL_THREADING_LAYER = 'SEQUENTIAL'
& D:/10_Projects/DOA_Estimation/.venvs/arena-gpu/Scripts/python.exe -m pytest -q
Set-Location frontend
npm run lint
npm test
npm run build
```

新建实验添加谱搜索算法，摘要应显示“实验统一网格／固定网格（无细化）”；修改统一步长后所有共享算法使用相同网格。显式选择局部加密才显示终止步长，切换独立网格才显示单独的起止角度和步长。复制旧 MUSIC 实验应保留“三点抛物线插值”。

## 3. 测试结果

- 本机 GPU 验收环境全套 `pytest -q`：**224 passed，206.85 秒**，包括 CUDA 测试；XML：`arena_ws/search_protocol/gpu_suite.xml`。
- 前端：**5 项通过**，ESLint、TypeScript 和 Vite 生产构建通过。
- `ruff check packages tests scripts`、`mypy packages`（101 文件）、OpenAPI 类型同步检查通过；本次提交全部文件 pre-commit 通过。
- 全仓库额外 pre-commit 探测发现既有非本次文件的格式问题（旧 Ruff 对 signals/generator.py、start_server.py 的提示及历史产物换行）；未纳入本次变更，工具自动改动已还原。本次提交检查全部通过。
- Python 运行有既有 Starlette TestClient 弃用提示及 JUnit record_property 警告，无失败/跳过。Linux CI 在推送后单独核对，不以本机结果代替。

专项 `tests/integration/test_search_protocol.py`：12 项通过，覆盖共享网格、独立扫描、不影响无网格算法、v1 三种 refine 情形、保存读取、中文路径、局部加密掩码/平滑/近邻峰/边界/空峰，以及 Schema 与规范化接口。

历史 MUSIC 输出与独立重建旧流水线使用 `assert_array_equal` 逐元素核对。两个原指标重算测试改用离网格角度，避免把“估计必然非零误差”当作测试前提；原始估计不变和门限重算的断言保留。

内置浏览器通过 HTTP 核对新默认、显式局部加密及旧实验复制。原型与实际页面均呈现统一网格入口、默认无细化策略。截图位于忽略目录 `arena_ws/search_protocol/explicit_variant.png`、`legacy_copy.png`。此次为变更相关页面验收，不重复声称全部产品页面重新验收。

## 4. 与设计文档的偏离

无未批准偏离。本次依据需求方确认同步调整正式设计文档并递增版本。前次数值复核报告中“局部加密作为默认”的建议已被公平对比方案取代；测量结果作为历史证据保留。

## 5. 需要需求方决定的问题

无。默认固定网格、关闭细化、显式可选变体及历史语义保留均已获批准。

## 6. 已知问题与建议

- 固定网格存在量化误差，真值落在网格上时可出现低于连续无偏 CRB 的样本 RMSE；不因此自动改网格、移动真值或优化算法。科研报告应同时记录网格步长和真值生成方式。
- 局部加密是可选数值变体，只细化已检出的粗峰，不保证恢复粗网格遗漏的谱峰。额外计算计入估计耗时。
- 固定网格要求步长整除范围，避免静默改步长；历史兼容网格保留旧端点行为。
- 前端构建仍有既有大分包提示。本轮未扩大到打包架构优化。
- 真实 AutoDL、Edge 专项、Word 报告继续按此前决定暂缓，与此次寻峰协议无关。
