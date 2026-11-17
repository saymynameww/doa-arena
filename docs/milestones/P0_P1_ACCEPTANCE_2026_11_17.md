> 六项后续收尾已完成，最新结论见 [闭环报告](P0_P1_CLOSURE_2026_11_17.md)。本文保留上一轮实测；耗时双列、响应测量、文档、最终 PDF 和参考硬件以新报告为准。

# P0/P1 产品补齐与验收报告

日期：2026-11-17。分支：`milestone/m7-benchmarks`。修复前基线：`82c2b481`。

## 1. 完成内容

本轮按需求方授权补齐 P0/P1，Word 暂缓、P2 不实施。需求规格第 3 章共 57 条 P0、28 条 P1，已逐行建立 [需求—组件—API—测试表](../prototype/P0_P1_TRACEABILITY.md)。这不是“85 个端到端自动测试”的声明；每条证据的范围和人工验收边界均在表中列出。

| 审计项 | 实现及结论 |
|---|---|
| A01 安装包前端 | 服务提供静态页面及 SPA 路由，未知 API/资源仍返回 404；构建脚本复制前端并清理旧 build，wheel 随包提供页面；隔离安装后不依赖 Node 即可访问 |
| A02 HTML/PDF 报告 | 配置参数、全部扫描点指标表、内嵌 SVG、打印入口与 A4 横向样式；使用网页同一图表生成器；失败算法不漏列，代码补丁正文保留在原始存档而不撑大报告 |
| A03 运行堆栈 | errors.json 分组、错误类型/次数、首次位置和完整 traceback 接通结果页；输出校验错误无堆栈时明确说明 |
| A04 CUDA 可用性 | 隔离子进程探测 cuda_available；设置和通用 Schema 设备选项禁用不可用 CUDA；GPU、CPU、未安装 torch 三种路径分别核查 |
| A05 插件检查 | `arena plugin check` 检查定义、输出、确定性、批量一致、输入不变、资源释放和全局随机状态；合理性给警告。违规夹具逐项检出，五个内置算法均通过 |
| A06 样式调整 | 字号、颜色、线型、标记按任务保存在本机浏览器；支持恢复默认；页面、表格和导出使用一致设置 |
| A07 Word | 需求方明确暂缓，不实现、不冒充通过 |
| A08 视觉身份 | 核心定义颜色/线型/标记，配置卡、结果表、曲线一致；首次失败算法仍保持配置顺序，参考线不受算法覆盖样式影响 |
| U01/U02 | 配置 JSON 文件导入经过后端校验；全局来源添加/移除闭环，移除仅取消登记，不删除文件 |

额外按正式文档发现并修正：默认快拍数 200、蒙特卡罗次数 500、单次省略次数为 1、中心间隔默认 10°、可选载频 null；移除非设计的快拍 10000 上限。既有显式配置保留，不改信号模型或算法公式，不递增 GENERATOR_VERSION。

运行进度补齐预计剩余时间和当前扫描点；PNG 按 300/96 倍输出满足 300 dpi 等效尺寸；MVDR 的 `info.used_pinv` 转为 Python bool，符合接口的 JSON 可序列化要求。比较页按对象数组中的字段展示差异，长补丁折叠，修复整页被补丁撑满的问题。

## 2. 怎么验收

```powershell
$env:PYTHONUTF8='1'
$env:MKL_THREADING_LAYER='SEQUENTIAL'
./start_dev.ps1 -NoBrowser -WithPrototype -PythonExecutable D:/10_Projects/DOA_Estimation/.venvs/arena-gpu/Scripts/python.exe -SequentialMkl
# 原型 http://127.0.0.1:4173/index.html，实际 http://127.0.0.1:3000
& D:/10_Projects/DOA_Estimation/.venvs/arena-gpu/Scripts/python.exe -m pytest
& D:/10_Projects/DOA_Estimation/.venvs/arena-learning/Scripts/python.exe -m pytest
& D:/00_Inbox/Anaconda/python.exe -m mypy packages
& D:/00_Inbox/Anaconda/python.exe scripts/generate_api_types.py --check
& D:/00_Inbox/Anaconda/python.exe scripts/build_release.py
# 只生成本机 wheel，不发布到 PyPI，不合并 main
arena plugin check music
Set-Location frontend
npm test
npm run lint
npm run build
```

模型插件可加 `--params params.json --workspace <目录> --device cuda`。插件必须来自已登记来源；检查运行于 CLI 进程，Web 服务不加载 torch。源码开发使用启动脚本；交付构建 wheel 安装后 `arena serve` 即可提供前端。

### 浏览器实际验收证据

以官方内置浏览器专用接口经 HTTP 操作原型和实际页面，本轮未使用文件协议、隐藏状态写入或其他浏览器控制绕行。

- `7a226f34`：通过文件选择器导入 JSON，2 点×10 次、MUSIC/TLS-ESPRIT/故意报错插件。完成 20 次共同数据试验，两个正常算法无错误，故障插件记录 20 次异常；结果页展开完整堆栈。
- 图表设为 18 号字、点划线和三角标记，刷新保留；通过页面下载 SVG，文件实含 `font-size: 18px` 和相应 dasharray。结果表标记同步。四个指标页签切换及已选状态读取耗时 307、313、314、322 ms（包括工具往返）。
- `9586cc2a`：2 点×10000 次、3 算法，60000 次提醒显示且允许提交。实际运行中显示 3776/20000、扫描点 1/2、预计剩余 138 秒；停止后保存 4480/20000，历史标记已取消，部分结果可查看并与完整任务比较。
- 模板、算法库、排行榜通过 HTTP 与原型截图对照；列表显示真实层级、来源、版本和状态。新工作目录排行榜显示尚无评测，未用假数据填充；正式九场景记录沿用 M7 报告。
- 比较页实际选择上述两个任务，展示 10000/10 次及字段差异、同指标叠加图和数值表。实测发现代码补丁撑满表格，修复后字段独立成行、长内容可展开。
- 独立安装包实例 `127.0.0.1:8766/settings`：显示 torch 未安装、cuda_available=false、CUDA 选项禁用；完成临时来源添加/移除，文件仍存在。隔离目录为 `arena_ws/p01_release_install`，未安装到基础环境。
- Chrome 曾正常打开产品并通过报告打印按钮保存 9 页 A4 横向 PDF（551185 B），使用 Poppler 渲染检查配置和指标页。此后增强打印表头黑色对比度和标题防孤行；内置浏览器报告内容复核通过。内置浏览器打印接口曾超时，PDF 保存实测证据来自 Chrome，二者不混写。

既有单次、蒙特卡罗、重算、备注、模型包、模板回收、工作目录切换、正式排行榜及中断整理交互证据见 [全产品视觉报告](FULL_VISUAL_ACCEPTANCE_2026_11_17.md) 和 [M7](M7.md)。本轮覆盖增量和页面回归，不声称所有历史场景本轮重新手工执行。

本地证据在忽略目录 `arena_ws/p01_acceptance/`：`import.json`、两个真实实验目录、`style-acceptance.jpg`、`progress-acceptance.jpg`、`report_print.pdf` 和 `print-*.png`。不提交实验、截图、权重、构建产物或缓存。

## 3. 测试结果

| 检查 | 结果 |
|---|---|
| GPU 全套 pytest（含 slow、CUDA、实际 MATLAB） | **191 passed、0 skipped、172.87 s** |
| CPU 全套 pytest（含 slow、实际 MATLAB） | **190 passed、1 skipped（CUDA）、179.63 s** |
| 前端单元测试 | **4 passed**，含新增长补丁/对象数组差异回归 |
| ESLint、TypeScript/生产构建 | 通过 |
| mypy | 99 源文件通过；排除打包生成的 build 副本 |
| ruff、OpenAPI 生成类型 | 通过 |
| NFR-20 指定工作负载 | M16/N200/K2、1000 次、五经典基线、0.1° 网格：**4.5489913 s <60 s** |
| GPU 批量与显存 | 实际 CNN 256 样本、5 轮中位数：7.209 ms/107.347 ms，**14.89 倍**；峰值 allocated 39,269,376 B，reserved 56,623,104 B，低于 8GiB |

日志与 JUnit：`arena_ws/p01_gpu_final.log/.xml`、`p01_cpu_final.log/.xml`；GPU 性能记录 `p01_gpu_performance.json`。测试使用原验收门限，未过滤 slow 或数值失败项。CPU 跳过 CUDA 是环境判定；GPU 环境不跳过该项。

插件检查首次发现 MVDR 的 NumPy bool 无法 JSON 序列化，测试先失败再修复；比较页对象数组回归同样先失败后通过。报告、静态资源、默认值、错误传播、图表身份、ETA、PNG 像素尺寸均有针对性回归。参考场景性能测试在正常固定种子下执行；不以总测试时间代替性能指标。

提交前钩子、最终安装包和提交后 Linux CI 的结果在本报告末尾追加，以避免将此前提交的 CI 冒充新提交验证。

## 4. 与设计文档的偏离

未私自修改正式设计文档。需求方批准的 10000 次阈值用于提示，不改变实验参数和执行；TLS 门限及正式九场景方案沿用既有批准。

本机实测硬件为 RTX 5060 Laptop 8GB，而文档参考机写 4060。量化结果对应真实硬件，不宣称测过 4060。正式页面使用动态 Schema 和真实数据，Ant Design 控件、表格内滚动及部分卡片留白与静态原型有差异；没有复制原型虚构模型、错误或任务数。

HTML 报告打印 PDF 符合架构 ADR-08；Word 暂缓符合本轮用户指令。算法样式保存在本机浏览器中，同一任务导出时传给核心；清除浏览器存储后会恢复默认，不改变存档的实验参数。

## 5. 需要需求方决定的问题

本轮无新增设计审批。已确认：Word 暂缓、P2 不做、真实 AutoDL 暂无实例保留待验、超过 10000 次仅提醒，以及继续使用内置浏览器验收。

## 6. 已知问题与建议

- **真实 AutoDL 待验**：Linux 自动化和本机 GPU 不能代替云端真实账号/实例工作流，按用户确认保留。
- **Edge 专项待验**：桌面接口无法可靠识别 URL 后按策略终止；用户指定改用内置浏览器完成本轮。不将此工具阻塞当作前端缺陷，也不声明 Edge 已通过。
- **NFR-21 是采样证据**：已测页签 <0.5 秒、运行不阻塞交互；不能据此保证任意插件/任意操作的最坏延迟。首次加载和子进程初始化仍有等待反馈。
- 现有 Vite 大包/CJS 提示及 Starlette 测试客户端弃用警告保留，未为消除警告升级依赖。GPU 示例模型准确率不是训练质量验收目标；插件检查的合理性为警告，不冒充科研精度结论。
- 需求方真实课题试用、合并 main 和发布标签仍由需求方进行。结论为：本轮授权的本机 P0/P1 实现补齐和对应验收已形成证据；外部专项及明确延期项保持开放，不能写为所有平台、全部产品设计无条件通过。

### 最终交付复核

- 提交前全部适用钩子通过，`git diff --cached --check` 通过；mypy 99 文件、OpenAPI 一致性再次通过。
- 最终前端重新生产构建；wheel 安装至独立的 `arena_ws/p01_release_final`，确认导入来自该目录，首页/历史/设置/健康检查均 200、两个实际静态资源 200、未知 API 404。没有改动基础或 CPU 环境的安装包。
- 比较页修复后通过内置浏览器截图复核：字段差异独立成行，长补丁默认折叠，结果图保持可见。证据：`arena_ws/p01_acceptance/comparison-acceptance.jpg`。
- 代码提交 `fc6dfceb26ea86eb43fcd9c33a356b25615500ee` 已推送；[Linux CI #44081849935](https://github.com/saymynameww/doa-arena/actions/runs/44081849935) 的 `linux-python310`（全套 pytest、mypy、生成类型）和 `linux-learning` 均为 success。随后报告提交仅补录证据，不修改代码。
- 钩子要求的 `isinstance` 类型联合写法调整后，额外回归：图表 15 passed（139.95 s）、产品补齐 8 passed（5.81 s）；不替代上面的 CPU/GPU 全套结果。
