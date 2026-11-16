"""DOA算法竞技场 - 核心库。

脚本模式门面，提供简洁的顶层API。
"""

__version__ = "0.1.0"  # 与发行包 pyproject.toml 一致；里程碑通过分支和报告标识。

# M2: 导出基础 API
from typing import Any

from .core import metrics
from .core.config import (
    AlgorithmConfig,
    ExperimentConfig,
    ExperimentType,
    ScenarioConfig,
    SweepConfig,
)
from .core.exploration import Scenario, algorithm, crb
from .core.facade import Workspace, algorithm_spec, finalize, load_result, recompute_metrics, run
from .core.runner import run_experiment


def __getattr__(name: str) -> Any:
    """云端数据生成无需安装绘图依赖，仅访问 figures 时加载 Plotly。"""
    if name == "figures":
        from .core import figures

        return figures
    raise AttributeError(name)


__all__ = [
    "__version__",
    "Scenario",
    "algorithm",
    "crb",
    "metrics",
    "figures",
    "Workspace",
    "algorithm_spec",
    "load_result",
    "run",
    "finalize",
    "recompute_metrics",
    "ScenarioConfig",
    "ExperimentConfig",
    "ExperimentType",
    "AlgorithmConfig",
    "SweepConfig",
    "run_experiment",
]
