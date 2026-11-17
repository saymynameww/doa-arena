# 本机 GPU 开发验收环境

日期：2026-11-17。需求方同意使用共享基础包的持久 venv 做开发验证。

## 配置与隔离

| 项目 | 实测 |
|---|---|
| 解释器 | `D:/10_Projects/DOA_Estimation/.venvs/arena-gpu/Scripts/python.exe` |
| Python | 3.14.6，来自 `D:/00_Inbox/Anaconda/python.exe` |
| PyTorch | 2.14.1+cu130，安装在新 venv 中 |
| CUDA 运行库 | 13.0 |
| NVIDIA GPU | GeForce RTX 5060 Laptop GPU，约 8 GB |
| 驱动 | 591.94（nvidia-smi 显示支持 CUDA 13.1） |
| 计算能力 | 12.0；PyTorch 编译架构列表包含 sm_120 |
| 通用依赖 | 复用基础 Anaconda，NumPy 2.4.6、SciPy 1.18.0 |

本环境以 `venv --system-site-packages` 创建，不是 conda 环境、不属于临时目录。它有独立包目录，允许读取基础环境通用包；基础包升级会影响本环境，因此适合本机开发验证，不能视作完全隔离的可搬运环境。

安装后核验：基础 Anaconda `find_spec('torch') is None`；原 `arena-learning` 环境仍为 torch 2.15.0+cpu。没有替换基础依赖、CPU 环境或系统 NVIDIA 驱动。CPU/GPU 数值一致性测试在同一个 GPU 环境内用同一份模型权重执行，不将两个不同 torch 版本的输出当作同版本对照。

## 来源与重建

使用 [PyTorch 官方 CUDA 13.0 索引](https://download.pytorch.org/whl/cu130/torch/) 返回的 Windows/Python 3.14 wheel：`torch-2.14.1+cu130-cp314-cp314-win_amd64.whl`。官方链接域名 `download-r2.pytorch.org`，大小 1,998,854,405 字节，SHA256：

```
e25757e423be3c107a36d7495fa5aeb021b9ab506457cd7c7e068505f0283ae0
```

普通 pip 下载长时间停滞，改为从官方 HTTPS 地址分段续传；逐段校验 Content-Range 和长度，合并后校验官方 SHA256，再由 pip 安装本地 wheel。未关闭 TLS 校验，未使用第三方包镜像。安装选择参考 [PyTorch 安装说明](https://pytorch.org/get-started/locally/)。

首次创建时运行（现有环境已经建好，无需重复）：

```powershell
& D:/00_Inbox/Anaconda/python.exe -m venv --system-site-packages D:/10_Projects/DOA_Estimation/.venvs/arena-gpu
& D:/10_Projects/DOA_Estimation/.venvs/arena-gpu/Scripts/python.exe -m pip install torch==2.14.1+cu130 --index-url https://download.pytorch.org/whl/cu130
```

## 使用

```powershell
$env:PYTHONUTF8='1'
$env:MKL_THREADING_LAYER='SEQUENTIAL'
& D:/10_Projects/DOA_Estimation/.venvs/arena-gpu/Scripts/python.exe -m pytest -q
./start_dev.ps1 -WithPrototype -PythonExecutable D:/10_Projects/DOA_Estimation/.venvs/arena-gpu/Scripts/python.exe -SequentialMkl
```

显式解释器路径无需激活环境。顺序 MKL 用于避免本机 Anaconda MKL 和 pip PyTorch 的重复 OpenMP 运行库，不使用跳过重复运行库检查的开关。Web 服务仍不加载 torch；环境探测和模型推理在独立核心进程中执行。当前开发服务已通过该 GPU 环境启动，原型仍通过 4173 端口提供。

## 验收结果

- `torch.cuda.is_available()` 为 True；实际 CUDA 张量矩阵乘法与同步完成。
- GPU 专项：1 passed、4 deselected、2.37 s。检查参数实际位于 CUDA，单模型批量推理与 CPU 输出按 float32 1e-6 容差比较，关闭后释放模型引用。
- GPU 环境全套：**170 passed、0 skipped、214.92 s**，包含实际 MATLAB 和 slow 测试。
- CPU 环境全套：169 passed、1 CUDA skipped、209.34 s。
- HTTP 实际模型任务 `ae143ed8` 完成 16 次双算法试验，模型配置 `device=cuda`、算法异常 0；真实 SNR=30 dB 超训练范围提示保留。此模型仅用于训练—导出—推理链路，不作为科研精度基线。
- 官方内置浏览器核验设置页：torch 2.14.1+cu130、CUDA 13.0、RTX 5060。截图 `arena_ws/m6_m7_acceptance/m7-gpu-environment.png`；测试日志 `m7_gpu_specific.log`、`m7_gpu_full.log`。
- Linux/Python 3.10 完整回归、Linux 学习链路通过 [CI 44022559535](https://github.com/saymynameww/doa-arena/actions/runs/44022559535)。本机 Python 3.14 通过不能替代 Linux 3.10，已分别验证。

## 保留边界与清理

真实 AutoDL 机器和账号流程仍未执行，本机 GPU 和 Linux CI 不替代该外部试用。GPU 环境会保留，可停止使用它的服务后删除整个 `arena-gpu` 目录；不会删除基础 Anaconda 或 `arena-learning`。

本次自动审批以策略拦截拒绝了删除下载缓存目录的操作，没有返回更具体原因，因此未绕过执行。`D:/10_Projects/DOA_Estimation/.venvs/gpu-wheel-cache` 内保留约 4 GB 的 wheel 和分段缓存；安装成功后运行环境已不依赖该目录，可由用户自行清理。大包、环境、缓存及实验结果均未提交 Git。
