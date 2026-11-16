# M5 测试结论报告

**测试日期**：2026-11-16
**测试范围**：M1–M5 后端核心、实验任务链路、API、前端真实数据联调与构建
**测试环境**：Windows；Python 3.14.6（Anaconda）；Node.js 24.22.1；npm 10.2.3
**结论**：**M5 功能回归通过，可进入验收；mypy 类型债务仍需后续专项治理**

## 1. 本轮修复

- 修复 ESPRIT 相位符号错误，LS/TLS 结果与 ULA 导向矢量定义一致。
- 修复测试随机数调用形态，统一使用固定 `default_rng` 派生，修复 `np.load(..., allow_pickle=False)`。
- 修复任务进度完成计数、结果顶层算法汇总及平均耗时字段。
- 增加真实图表、导出、模板 API；前端图表、导出、模板、对比页面改为读取后端数据。
- 修复未知算法返回 HTTP 404、前端 TypeScript 编译错误和 ESLint 配置问题。
- 完成 Ruff 格式化与 lint 清理。

## 2. 验收命令与结果

```powershell
D:\00_Inbox\Anaconda\python.exe -m pytest -q
D:\00_Inbox\Anaconda\python.exe -m ruff check packages tests
D:\00_Inbox\Anaconda\python.exe -m ruff format --check packages tests
cd frontend
npm run lint
npm run build
```

结果：

- pytest：**54 passed, 1 skipped**；跳过项为未安装 Kaleido 的图表导出测试。
- Ruff lint：**通过**。
- Ruff format：**通过**。
- 前端 ESLint：**通过，0 errors / 0 warnings**。
- 前端 TypeScript/Vite build：**通过**。
- 集成 Web Service/Runner 回归：**18 passed**。

## 3. 关键链路

后端健康检查、算法列表、实验提交、任务状态、结果读取、SSE 进度、真实图表数据、JSON/NPZ/CSV/MAT/TeX/HTML 导出、模板增删改查均已接入实现并通过现有 API 集成测试。任务完成事件的 `completed_trials` 与结果汇总字段已修复。

## 4. 未完成项与限制

`mypy` 当前仍报告 87 个类型错误，主要集中在 Pydantic/NumPy 类型推导、插件抽象接口签名和旧有导出数据的宽类型。这些问题不影响本轮 pytest、API 集成和前端构建，但应作为 M6 类型治理任务继续处理。Kaleido 未安装，因此对应图表静态导出测试自动跳过；安装依赖后需补跑该项。浏览器视觉端到端验收仍未执行。

## 5. 结论

M5 运行功能和前端构建阻塞问题已修复，全套 pytest 回归通过。当前代码可提交 M5 需求方验收；验收时建议补装 Kaleido，并安排浏览器端到端和 mypy 专项检查。
