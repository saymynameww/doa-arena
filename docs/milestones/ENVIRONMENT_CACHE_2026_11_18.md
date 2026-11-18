# 环境检测缓存与新建实验加载优化

日期：2026-11-18。分支：`codex/environment-cache`。基线：`4d653d05`。

## 1. 完成内容

按需求方批准的方案，环境检测改为服务启动时后台执行，结果保存在该服务实例中。GET 只读取快照；手动 POST 刷新启动后台任务，同一时间的重复请求合并。切换页面、刷新浏览器、切换工作目录均不清空服务缓存；服务重启创建新缓存。

新建实验只等待 Schema 和模板，不再等待环境检测。环境完成后仅更新设备选项，不重建实验草稿。设置页增加“重新检测”，检测中、CUDA 可用、CUDA 不可用、检测失败分别表示；失败的可用性为 null，不能冒充无 CUDA。新建实验使用模型设备字段时也显示“检测中／检测失败”。CPU 配置不受检测等待影响。

探测仍由独立 Python 进程加载 torch，Web 进程不加载 torch；120 秒超时及服务关闭会回收探测子进程。模型实际运行前沿用 `ModelAlgorithm.setup` 的设备可用性检查，显式 CUDA 不可用时报错，不改成 CPU。

## 2. 怎么验收

```powershell
./start_dev.ps1 -PythonExecutable D:/10_Projects/DOA_Estimation/.venvs/arena-gpu/Scripts/python.exe -SequentialMkl
python -m pytest tests/integration/test_environment_cache.py -q
python -m pytest -q
python scripts/generate_api_types.py --check
```

打开新建实验，表单不应等待 GPU 探测；到设置页点击“重新检测”，检测期间可切回新建实验正常编辑。完成后设置页显示实际设备。多次打开页面只读缓存；安装依赖或切换解释器后重启服务。

接口：`GET /api/settings/environment` 返回 `EnvironmentStatus`（status、cuda_available、details、error、checked_at）；`POST /api/settings/environment/refresh` 立即返回 detecting。OpenAPI 生成的前端类型已同步。检测期间前端每 500 ms 只读取快照，完成／失败或卸载后停止轮询。

## 3. 测试结果

性能实测（同机开发服务、内置浏览器）：

| 项目 | 优化前 | 优化后 |
|---|---|---|
| 环境接口 | 5.988 s、4.482 s | 启动探测尚在进行时读取缓存 10.68、1.54、23.98 ms |
| Schema 接口 | 81、61 ms | 重启后 107.07、34.87、60.73 ms |
| 模板接口 | 7、18 ms | 6.03、3.99、7.58 ms |
| 新建实验表单显示 | 原 Promise.all 必须等环境请求完成 | 155.8、155.7、151.5 ms |

表单计时使用开发模式 `?uiAudit=1`：从表单请求发起到 React 提交表单 DOM 后下一帧绘制后的任务，不使用自动化工具往返时间；不含首次开发 JS 下载、也不包含随后异步生成的场景预览。生产构建不包含 `ARENA_CONFIG_READY` 日志。上述是本机采样，不是任意插件数量或硬件的最坏上界。

内置浏览器实际点击重新检测并切换新建实验，表单正常显示；返回设置页确认 RTX 5060 Laptop、CUDA 13.0 和检测完成状态，截图 `arena_ws/environment_acceptance/settings.jpg`。首次浏览器连接超时后正常重试成功，没有绕过安全策略。

新增 4 项自动化测试通过：未完成探测不阻塞启动/Schema、重复 GET/POST 合并、缓存及服务重启、失败与手动恢复、关闭时取消检测、子进程回收（部分条件在同一测试中）。

| 验证 | 结果 |
|---|---|
| Windows GPU 全套 | 204 passed，191.04 s |
| Windows CPU 全套 | 203 passed、1 skipped（无 CUDA），257.03 s |
| 提交前非慢速回归 | 182 passed、1 skipped、21 deselected，64.29 s |
| 前端 | 4 tests passed；ESLint、TypeScript、Vite build 通过 |
| 静态检查 | mypy 101 个文件通过；OpenAPI 类型一致；适用 pre-commit 钩子全部通过 |
| Linux Python 3.10 全套 | 198 passed、6 skipped（缺少 torch / MATLAB），60.85 s；类型和 OpenAPI 检查通过 |
| Linux 学习流程 | 12 passed、1 skipped（无 CUDA），6.71 s |

代码提交 `a5436888ccf0eaa6cdeca1dd2c0dd2d20534b26b` 的 [Linux CI 44253903082](https://github.com/saymynameww/doa-arena/actions/runs/44253903082) 两个任务通过。

本机完整回归覆盖新增缓存测试及既有算法、GPU、导出、报告和 Web 流程；保留已有 Starlette/httpx、JUnit record_property 警告及前端大包提示。原始日志/XML 在 `arena_ws/environment-*.log/xml`，加载采样及截图在 `arena_ws/environment_acceptance/`。缓存完成后连续五次 GET 保持相同 checked_at，耗时为 29.22、3.27、3.67、3.97、3.56 ms。

## 4. 与设计文档的偏离

无算法、实验结果或正式设计文档变更。本次环境接口增加状态包装和手动刷新路由，属于需求方明确批准的交互调整；仓库内两个消费者及自动生成类型同步更新。

## 5. 需要需求方决定的问题

无新增决定。修复分支完成后提交推送，合并 main 待需求方确认。

## 6. 已知问题与建议

外部插件的发现仍可能影响 Schema 耗时，本次只解决已实测的环境检测阻塞。首次下载开发资源和场景预览属于独立耗时，不能混同为表单等待环境检测。AutoDL、Edge、Word 和 P2 范围不变。
