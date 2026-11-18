# Kaleido 静态导出故障修复与验收

日期：2026-11-18。分支：`codex/fix-kaleido-export`。基线：`8384a2b`。

## 1. 完成内容

问题来自 [Linux CI 44092029219](https://github.com/saymynameww/doa-arena/actions/runs/44092029219)：两次运行均在 PNG 导出时出现 `ReferenceError: kaleido_scopes is not defined`。

根因证据：本机原始 `fig.to_image()` 三次最小图导出中复现一次。失败前通过浏览器运行时读取到目标为 Kaleido 临时 `index.html`，`document.readyState=loading`，`typeof kaleido_scopes=undefined`，`typeof Plotly=undefined`；此时 DOM 仅解析到首个外部 MathJax 脚本。随后调用导出立即出现同样的 ReferenceError。另两次调用开始时为 complete，两个对象均存在，导出成功。这证明就绪事件与实际脚本就绪状态存在竞态，不是算法计算失败，也不是缺少 Kaleido。

Kaleido 1.5.1 的导航实现只等待 `Page.loadEventFired` 和执行上下文事件，没有核验目标页导出函数。MathJax 的外部加载延长了故障窗口；没有证据认定某次 CDN 服务故障或特定 Chrome 版本是唯一原因。

修复：在 `core.figures.render` 使用 Kaleido 公共浏览器接口，逐页确认文档 complete、Plotly 存在、`kaleido_scopes.plotly` 为函数，再执行渲染。检查最多等待 90 秒；超时和协议错误明确报错，不重试整张图，不吞异常，不修改第三方安装文件。每次调用独立回收浏览器与线程，可供已有异步循环的调用方使用。

PNG、SVG、PDF 以及 HTML 报告内嵌 SVG 统一走此路径；保留 300 dpi 等效 PNG、图表/模板尺寸优先级以及 Plotly 的 MathJax/Plotly.js 配置。绘图依赖下限更新为实际采用的公开接口版本，`pypdf` 仅用于开发测试。CI 记录绘图依赖版本和下载的 Chrome 路径。

## 2. 怎么验收

在仓库根目录、安装 `doa-arena[dev,server,plot]` 的环境运行：

```powershell
python -c "import kaleido; kaleido.get_chrome_sync()"
python -m pytest tests/integration/test_static_render.py tests/integration/test_figures.py -q
python -m pytest -q
python -m mypy packages
python scripts/generate_api_types.py --check
```

`test_export_waits_for_delayed_renderer` 对三种格式注入 750 ms 的导出函数不可用窗口，真实调用 Chrome 导出。将生产入口恢复为旧 `fig.to_image` 后 PNG 回归稳定失败（undefined 的 plotly 属性访问）；新入口三格式全部通过。另有超时与协议失败测试，保证不会伪报成功。

## 3. 测试结果

| 项目 | 结果 |
|---|---|
| Windows GPU 最终代码全套 | 200 passed；RTX 5060 Laptop 环境；152.66 s（初轮 200 passed / 203.00 s） |
| Windows CPU 全套 | 199 passed、1 skipped（无 CUDA）；192.24 s |
| 最终导出专项（含报告与延迟初始化） | 20 passed；45.07 s；Plotly 7.1.0 / Kaleido 1.5.1 / Choreographer 1.4.0 |
| 前端 | 4 tests passed；ESLint、TypeScript、Vite build 通过 |
| 类型与接口 | mypy 100 个源文件通过；OpenAPI 类型一致性通过 |
| 提交前非慢速测试 | 178 passed、1 skipped（无 CUDA）、21 deselected；73.58 s；全部适用 pre-commit 钩子通过 |
| PNG | 640×480 逻辑尺寸导出 2000×1500；验证 PNG 文件头与 IHDR |
| SVG | XML 可解析，存在曲线路径与中文图例 |
| 图表 PDF | pypdf 解析成功，单页、页面宽度和内容流符合预期；Poppler 渲染后目视检查通过 |
| HTML/PDF 报告 | 四张图、六行指标、双耗时列和完整配置；HTML 转为 9 页 A4 横向 PDF，逐页渲染检查通过 |
| Linux Python 3.10 全套 | 194 passed、6 skipped（无 torch / MATLAB）；57.75 s；mypy、OpenAPI 一致性通过 |
| Linux 学习流程 | 12 passed、1 skipped（无 CUDA）；8.42 s |

最终代码提交 `bdb01f549e9d0262882f94e0cb0399d980091ba6` 的 [Linux CI 44210820985](https://github.com/saymynameww/doa-arena/actions/runs/44210820985) 两个任务均为 success；没有跳过静态导出测试。GPU/CPU 初轮完成后补充了模板尺寸优先级及报告内容断言，最终导出专项、GPU 全套和 Linux 全套均已覆盖。警告为已有的 Starlette/httpx 弃用提示、JUnit `record_property` 格式兼容提示；前端保留已有的大包提示。

本机证据在忽略目录 `arena_ws/kaleido_acceptance/`（三格式图、HTML、PDF、九页图片）；测试日志及 XML 为 `arena_ws/kaleido-*.log/xml`。PDF 沿用需求方已批准的 WeasyPrint 离线排版加逐页检查方式，不将其称为原生浏览器打印验收。

## 4. 与设计文档的偏离

无产品需求或算法语义变更。仅修复导出时序并补齐测试，正式设计文档未修改。Kaleido 的 Chrome 依赖及静态输出用途见 [Plotly 官方文档](https://plotly.com/python/static-image-export/)。

## 5. 需要需求方决定的问题

无新增设计决策。修复留在独立分支，合并 main 仍待需求方决定。

## 6. 已知问题与建议

本修复解决脚本尚未就绪即导出的竞态。环境缺少 Chrome、资源永久不可达等仍应返回错误，不能把等待机制当作依赖修复。自定义 MathJax/Plotly.js 资源须可访问；未宣称所有第三方浏览器/脚本组合均已验证。真实 AutoDL、Edge 专项、Word 报告继续暂缓，P2 不在范围。
