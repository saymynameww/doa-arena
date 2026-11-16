"""DOA算法竞技场 - 核心库。

脚本模式门面，提供简洁的顶层API。
"""

__version__ = "0.3.0"  # M3 版本

# M2: 导出基础 API
from .core.config import (
    AlgorithmConfig,
    ExperimentConfig,
    ExperimentType,
    ScenarioConfig,
    SweepConfig,
)
from .core.facade import Workspace, algorithm_spec, load_result, recompute_metrics, run
from .core.runner import run_experiment

__all__ = [
    "__version__",
    "Workspace",
    "algorithm_spec",
    "load_result",
    "run",
    "recompute_metrics",
    "ScenarioConfig",
    "ExperimentConfig",
    "ExperimentType",
    "AlgorithmConfig",
    "SweepConfig",
    "run_experiment",
]
