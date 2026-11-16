# M1–M5 重新验收记录

日期：2026-11-16。分支：`codex/m5-product-refactor`。
结论：本轮自动化测试通过；整体 M5 验收仍未完成。
早期报告的“完整”“全部完成”不能替代本次逐项验收结果。

## 1. 完成内容

- 数值基线：修正 Root-MUSIC 符号、谱峰边界、插值、归一化、自动平滑孔径、MVDR 加载和伪逆；补充接口规范 13.4 验收测试。
- 信号与下界：完整随机信号 CRB、复相关矩阵半正定检查、相干信源逐源功率、逐次相干相位、随机角度拒绝采样、随机 K 权重和 63 位种子。生成器版本为 3。
- 运行：算法跨扫描点复用、退出资源释放、错误隔离、取消和部分结果保存；Web 实验改为独立 spawn 子进程。
- 插件：文件/子目录入口发现、相对导入、失败隔离、来源记录；发现使用子进程。
- 结果：逐次真值和真实空间谱保存与读取，按信源匹配的误差分布；CSV、MATLAB、LaTeX 使用实际真值与配置门限。
- 脚本：`Workspace`、`algorithm_spec`、`Algorithm.spec`、`arena.run`、`load_result` 和 `python -m arena run`；规范配置读取与写出；Web 从文件恢复脚本实验历史。
- 类型检查：消除已发现的接口不一致与类型错误，未关闭 mypy 检查。

## 2. 怎么验收

```powershell
python -m pytest -q
python -m mypy packages
python -m ruff check packages tests scripts/audit_esprit_efficiency.py
python scripts/audit_esprit_efficiency.py
cd frontend
npm run build
```

浏览器验收使用 `start_dev.ps1 -WithPrototype` 提供的 HTTP 页面。
原型为 `http://127.0.0.1:4173/index.html`，实际界面为 `http://127.0.0.1:3000`。

## 3. 测试结果

门限批准并纳入历史重建用例后的全套运行：108 通过，0 失败，1 条第三方 Starlette 弃用警告，50.04 秒。
脚本与 Web 定向回归：16 通过，8.83 秒。提交前检查通过，前端 ESLint 通过。
mypy：72 个源文件通过。Ruff 检查通过。前端生产构建通过，主包约 5.98 MB，仍有体积警告。

TLS-ESPRIT 独立实现复核的最大角度差为 2.86×10⁻¹³ 度。
规定场景 10–30 dB、四组各 500 次试验的效率比为 1.786–1.881。
具体证据与批准记录见 [门限复核报告](TLS_ESPRIT_THRESHOLD_REVIEW.md)。

## 4. 与设计文档的偏离

以下事项仍待实现或完整核查，不能因现有测试通过而视为符合设计：

- 完整并行执行、批量推理、信源数估计和各保存选项的真实行为。
- 所有插件类型及模型包流程、完整能力校验与警告。
- SQLite 可重建索引、完整结果文件契约、版本追溯和错误详情。
- 完整脚本细粒度 API、指标重算、正式场景集和版本隔离排行榜。
- 前端 OpenAPI 类型生成、各页面完整交互和原型视觉对齐。
- Linux / Python 3.10 的实际运行验证，GPU / MATLAB 环境专项验证。

## 5. 需要需求方决定的问题

TLS-ESPRIT 门限已获批准：只在规范规定场景改为 `<2.0`，Root-MUSIC 保持 `<1.5`。
接口规范更新为 v0.6；算法公式不变。当前没有新增设计决策请求。

## 6. 已知问题与建议

已通过 HTTP 实际查看原型新建实验页。切换实际界面时，Computer Use 因无法可靠识别当前浏览器 URL 而停止；该次正式页面视觉对照没有完成，不能记录为通过。
需继续完成上述差距、逐项视觉验收、全套回归及追踪表核对后，才能将 M5 标为通过。
