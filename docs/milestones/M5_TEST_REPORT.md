# M5 重构后测试结论报告

**测试日期**：2026-11-16  
**测试范围**：核心算法、后端 API、任务持久化、Schema 配置、模板/设置/工作目录、历史实验、结果导出、前端数据流和生产构建  
**测试环境**：Windows；Python 3.14.6（Anaconda）；Node.js 24.22.1；npm 10.2.3  
**结论**：**功能重构通过，已具备需求方验收条件**

## 1. 本轮完成内容

- 保留 `arena_api`、`arena.core`、算法实现、Runner 和现有测试体系。
- 新增 `/api/schema/experiment`，前端配置页改为读取 Schema，并完整提交阵列、信源、角度、SNR、误差和算法参数。
- 任务索引落盘，后端重启后可以恢复历史任务。
- 新增设置、工作目录和索引重建接口。
- 完善模板创建、读取、编辑、删除和回收站流程。
- 完善历史实验复制、重跑、删除和批量对比约束。
- 完善 JSON、NPZ、CSV、MAT、LaTeX、HTML、PNG、SVG、PDF 和 Python 脚本导出。
- 修复图表真值角度硬编码，结果页导出和全屏按钮接入真实行为。
- 新增 Schema、设置和模板接口集成测试。

## 2. 验收结果

```powershell
D:\00_Inbox\Anaconda\python.exe -m pytest -q
D:\00_Inbox\Anaconda\python.exe -m ruff check packages tests
D:\00_Inbox\Anaconda\python.exe -m ruff format --check packages tests
cd frontend
npm run lint
npm run build
```

结果：

- pytest：**56 passed，1 skipped**；跳过项为未安装 Kaleido 的静态图导出测试。
- Ruff lint：**通过**。
- Ruff format：**通过**。
- 前端 ESLint：**通过，0 errors / 0 warnings**。
- 前端 TypeScript/Vite build：**通过**。
- Web Service/Runner 集成测试：**20 passed**，包含 Schema、设置和模板接口。
- 运行中的服务验证：后端 `/api/health` 返回 `ok`，Schema 返回 5 个算法，前端返回 HTTP 200。

## 3. 当前仍需安排的专项工作

`mypy` 仍报告约 87 个历史类型错误，主要集中在 Pydantic/NumPy 类型推导、插件抽象接口签名和旧有宽类型数据结构。这些问题不影响本轮功能回归、API 集成或前端生产构建，建议作为后续类型治理专项处理。

Kaleido 未安装，因此 PNG/PDF/SVG 的自动化导出测试被跳过；安装 Kaleido 后需要补跑该测试。浏览器视觉验收仍需在需求方环境中完成一次。

## 4. 结论

当前分支已经完成产品层重构的功能范围，前后端数据流已从模拟/内存实现切换为真实 API。核心算法和已有测试保持通过，代码已分阶段提交推送，建议需求方基于该分支进行原型验收。
