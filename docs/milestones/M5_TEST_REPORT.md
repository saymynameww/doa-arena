# M5 测试结论报告

**测试日期**：2026-11-15  
**测试范围**：M1–M5 当前代码、后端接口、前端构建与 M5 关键链路  
**测试环境**：Windows；Python 3.14.6（Anaconda base）；Node.js 24.22.1；npm 10.2.3  
**结论**：**不通过，暂不建议进入 M6 验收**

## 1. 完成内容

本次执行了以下测试：

- 后端 pytest 非慢速回归测试和完整回归测试。
- `ruff check`、`ruff format --check`、`mypy`。
- 前端 `npm run lint` 和 `npm run build`。
- 后端健康检查、算法列表、算法详情、实验提交、任务状态、结果读取。
- SSE 进度订阅。
- 前端 Vite 开发服务器和静态资源 HTTP 可访问性。
- 项目硬性规则的静态扫描：随机数、顶层 PyTorch 导入、不安全文件读取。
- 浏览器自动化验收未完成：Computer Use 无法安全识别当前浏览器 URL，按工具安全要求停止。

## 2. 怎么验收

### 2.1 已执行命令

```powershell
D:\00_Inbox\Anaconda\python.exe -m pytest -m "not slow" -q
D:\00_Inbox\Anaconda\python.exe -m pytest -q
D:\00_Inbox\Anaconda\python.exe -m ruff check packages tests
D:\00_Inbox\Anaconda\python.exe -m ruff format --check packages tests
D:\00_Inbox\Anaconda\python.exe -m mypy
cd frontend
npm run lint
npm run build
```

### 2.2 后端接口验收

已验证：

- `GET /api/health` 返回 HTTP 200，状态为 `ok`。
- `GET /api/algorithms` 返回 HTTP 200，并列出内置算法。
- 可提交蒙特卡罗实验并获得任务 ID。
- 任务状态可从 `running` 变为 `completed`。
- `GET /api/experiments/tasks/{id}/result` 返回结果目录和文件清单。
- SSE 端点返回 `text/event-stream`，能够收到 `running` 和 `completed` 事件。
- 无效实验配置能够返回 HTTP 400 和中文错误信息。

### 2.3 前端服务验收

Vite 开发服务器能够启动，以下地址返回 HTTP 200：

- `http://127.0.0.1:3000/`
- `http://127.0.0.1:3000/src/main.tsx`
- `http://127.0.0.1:3000/src/App.tsx`

这只能证明开发服务器能提供资源，不能替代生产构建和浏览器流程验收。

## 3. 测试结果

### 3.1 后端 pytest

| 测试集 | 结果 |
|---|---|
| 非慢速测试 | 51 通过，1 失败，1 跳过，2 个慢速测试未执行 |
| 完整测试 | 53 通过，1 失败，1 跳过 |
| 失败测试 | `tests/unit/api/test_kit.py::test_esprit` |
| 跳过测试 | `tests/integration/test_figures.py` 中 Kaleido 依赖测试 |
| 警告 | Starlette 的 `httpx` 兼容性弃用警告 |

失败原因：ESPRIT 单元测试要求估计误差小于 3°，实际 LS-ESPRIT 输出为 `[-15°, 20°]`，真值为 `[-20°, 15°]`，误差为 5°。该失败与 M1 报告中记录的 ESPRIT 低 SNR 精度问题一致，但当前仍然使完整回归不通过。

### 3.2 静态检查

| 检查 | 结果 |
|---|---|
| Ruff lint | 失败，发现 194 个错误 |
| Ruff format | 失败，26 个文件需要格式化 |
| mypy | 失败，发现 89 个类型错误，涉及 26 个文件 |
| 前端 ESLint | 失败，项目没有 ESLint 配置文件 |
| 前端 TypeScript/Vite build | 失败，多处 TypeScript 编译错误 |

前端构建错误包括未使用导入、`ConfigSummary` 缺少 `Space` 导入、Plotly layout 类型不匹配、Ant Design `Collapse` 属性错误、Select 回调类型错误，以及 `TaskProgress.completed_trials` 类型不一致。

### 3.3 后端真实实验链路

使用 `M5 API验收` 配置运行 2 次试验的 MUSIC 蒙特卡罗实验：

- 任务提交成功。
- 任务最终状态为 `completed`。
- 生成 `config.json`、`meta.json`、`results.npz`、`summary.json`。
- `results.npz` 使用 `allow_pickle=False` 读取成功，包含估计值、耗时和失败标记。
- `summary.json` 中 MUSIC 的 RMSE 和成功率有数值。

发现两个数据一致性问题：

1. 任务完成时进度仍为 `completed_trials: 0`，但 `percent` 为 100%。
2. `summary.json` 顶层 `algorithms` 为空数组，算法汇总实际位于 `points[].algorithms`。

这会影响前端进度显示、结果表格和依赖顶层算法列表的逻辑。

### 3.4 SSE

SSE 能收到两个事件：

```text
running: completed_trials = 0, percent = 0
completed: completed_trials = 0, percent = 100
```

连接和终止行为正常，但完成事件中的试验计数错误，判定为结果展示缺陷。

### 3.5 M5 前端实现核查

源码检查确认以下功能仍未接通真实后端：

- `ResultCharts.tsx` 使用硬编码模拟图表数据，并保留“从后端加载图表数据”的 TODO。
- `ExportMenu.tsx` 使用延时模拟导出，没有调用后端导出 API，也不会产生真实文件。
- `Templates.tsx` 使用硬编码模板，使用模板只显示成功消息，删除只修改内存状态。
- `Compare.tsx` 使用模拟对比数据。

这些问题与 M5 报告中的已知问题一致，属于核心结果流程缺陷。

### 3.6 项目硬性规则扫描

静态扫描发现：

- 测试代码中多处使用 `np.random.randn`、`np.random.rand`，违反项目对随机数 API 的约定。
- `tests/integration/test_runner.py` 中调用 `np.load` 时未显式传入 `allow_pickle=False`。
- PyTorch 导入位于函数内部，未发现模块顶层直接导入；当前 `torch.load` 调用已使用 `weights_only=True`。

## 4. 与设计文档的偏离

1. M5 报告声称前端核心流程完成，但当前图表、导出、模板和对比功能仍有模拟或内存实现。
2. M5 报告声称 TypeScript 严格构建通过，当前 `npm run build` 实际失败。
3. M5 报告声称 ESLint 检查通过，当前项目缺少 ESLint 配置文件，`npm run lint` 无法执行。
4. 后端结果结构与 M5 前端预期之间存在字段不一致，尤其是进度计数和汇总顶层算法列表。
5. 浏览器端到端验收未完成，因此不能确认页面交互、路由和视觉布局全部符合原型。

## 5. 需要需求方决定的问题

### 问题 1：M5 是否以真实数据联调为通过条件？

推荐：**必须通过**。

如果图表、导出、模板和对比继续使用模拟数据，M5 只能视为界面原型完成，不能视为可交付的前端阶段。

### 问题 2：ESPRIT 低 SNR 测试如何处理？

推荐：保留算法行为，修正测试场景或验收阈值，并补充高 SNR 验收测试；不要修改基线算法只为通过曲线检查。

### 问题 3：是否允许先修复前端构建阻塞项再继续浏览器测试？

推荐：先修复 TypeScript 编译错误和 ESLint 配置，再进行浏览器端到端验收。

## 6. 已知问题与建议

### 阻塞问题

- P0：前端生产构建失败。
- P1：完整 pytest 回归失败。
- P1：图表使用模拟数据。
- P1：导出菜单不产生真实文件。
- P1：模板和对比页面未连接持久化/真实结果。
- P1：SSE 完成进度和结果汇总字段不正确。
- P1：mypy 发现 89 个类型错误，说明接口类型存在较大不一致。

### 建议修复顺序

1. 修复前端 TypeScript 编译错误，补齐 ESLint 配置。
2. 补充前端 API：真实图表数据、导出、模板、历史和对比数据。
3. 修复 Runner/TaskManager 的完成试验计数和结果汇总结构。
4. 处理 ESPRIT 测试场景或验收阈值，并保留高 SNR 基线测试。
5. 修复 `ruff`、`mypy` 和测试中的随机数/`np.load` 规则问题。
6. 安装并验证 Kaleido，再执行图表导出测试。
7. 重新执行浏览器端到端验收，并补充 Vitest 或 Playwright 自动化测试。

当前结论是：后端基础实验服务可运行，M5 前端代码尚未达到可验收交付状态。
