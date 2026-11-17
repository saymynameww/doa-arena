# doa-arena 安装与使用

当前参考机器：Windows、RTX 5060 Laptop GPU（8 GB）。支持 Python 3.10 及以上；PyTorch 可选。所有命令从仓库根目录执行。不要在基础 Anaconda 中升级依赖；已有 `arena-learning` / `arena-gpu` 验收环境可直接复用。

## 独立开发环境（PowerShell）

```powershell
conda create -n doa-arena-dev python=3.12 -y
conda activate doa-arena-dev
python -m pip install -e packages/arena_api -e "packages/arena[dev,server,plot]" pre-commit httpx
Set-Location frontend
npm ci
Set-Location ..
pre-commit install
```

上面创建独立环境，不修改 base。首次静态图导出如提示缺少 Chrome，可执行 `python -c "import kaleido; kaleido.get_chrome_sync()"` 下载绘图引擎。

GPU 可选安装（本机已验证 CUDA 13.0 构建及 RTX 5060 Laptop）：

```powershell
python -m pip install torch==2.14.1+cu130 --index-url https://download.pytorch.org/whl/cu130
python -c "import torch; print(torch.__version__, torch.cuda.is_available()); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU')"
```

安装命令需要与所用 Python、Windows 和 NVIDIA 驱动兼容。既有 GPU 验收环境使用 Python 3.14；上面的独立 conda 环境可选择官方提供对应 wheel 的 Python 版本。CUDA wheel 自带运行时，无需为了推理安装完整 CUDA Toolkit。没有 CUDA 时跳过此步，经典算法正常使用。云端镜像已有 torch 时只安装核心库，不执行 torch 安装命令，以保留原版本。

## 开发启动与原型

```powershell
./start_dev.ps1 -WithPrototype -PythonExecutable (Get-Command python).Source
# 本机保留的 GPU 验收环境：
./start_dev.ps1 -WithPrototype -PythonExecutable D:/10_Projects/DOA_Estimation/.venvs/arena-gpu/Scripts/python.exe -SequentialMkl
```

脚本停止其管理端口上的旧服务后重新启动。实际页面 `http://127.0.0.1:3000`，后端 `http://127.0.0.1:8765`，原型 `http://127.0.0.1:4173/index.html`。加 `-NoBrowser` 可不自动打开浏览器。`-SequentialMkl` 用于本机 Anaconda MKL 与 PyTorch 的 OpenMP 运行库兼容。服务只监听本机。

## 构建和安装交付包

构建者需要 Node；交付包使用者不需要 Node。构建脚本将最新前端资源打入 wheel，并清除旧哈希资源：

```powershell
python scripts/build_release.py
python -m pip wheel --no-deps packages/arena_api --wheel-dir dist
# 在独立的目标环境中安装，不在已有开发环境中覆盖：
python -m pip install dist/doa_arena_api-1.0.0-py3-none-any.whl "dist/doa_arena-0.1.0-py3-none-any.whl[server,plot]"
arena serve --port 8765
```

随后打开 `http://127.0.0.1:8765`。源码可编辑安装没有前端产物时请使用开发启动脚本，或先运行构建脚本。`arena serve` 启动本机服务；自动打开页面由 `start_dev.ps1` 完成。不要求发布到 PyPI。

## 脚本模式（可直接运行）

```python
from pathlib import Path
import arena

config = {"name": "文档示例", "type": "monte_carlo", "trials": 3,
          "algorithms": [{"id": "music"}]}
result = arena.run(config, workspace=Path("arena_workspace"))
restored = arena.load_result(Path("arena_workspace"), Path(result.metadata["directory"]).name)
assert len(restored.points[0].trials) == 3
sample = arena.Scenario({}).sample(trial_index=0, seed=42)
print(sample.observation.X.shape)
```

将上面的 config 保存成 JSON 后也可使用 `arena run config.json --workspace arena_workspace`。批量数据集用 `arena dataset generate dataset.json --out datasets/demo`；配置结构见数据格式规范。索引在启动时根据实验目录恢复，或通过 Web 设置中的重建入口处理；没有 `arena index rebuild` 命令。

```powershell
arena --help
arena plugin check music
arena schema export --out arena_ws/schema.json
python -m pytest
python -m mypy packages
python scripts/generate_api_types.py --check
Set-Location frontend
npm test
npm run lint
npm run build
```

插件检查覆盖输出、确定性、批量一致、输入保护及资源释放；模型插件需 `--params` 提供模型包，必要时加 `--workspace` 和 `--device cuda`。它是开发验证工具，不证明模型科研精度。

依赖统一以各包 `pyproject.toml` 为准。详细接口见 `docs/03_算法接口规范.md`，数据格式见 `docs/04_数据格式规范.md`，当前验收见 `docs/milestones/P0_P1_CLOSURE_2026_11_17.md`。Word、真实 AutoDL、Edge 专项继续暂缓。
