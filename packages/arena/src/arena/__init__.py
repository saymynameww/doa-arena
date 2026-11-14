"""DOA算法竞技场 - 核心库。

脚本模式门面，提供简洁的顶层API。
"""

__version__ = "0.2.0"  # M2 版本

# M2: 导出基础 API
from .core.config import ExperimentConfig, ExperimentType, ScenarioConfig
from .core.runner import run_experiment

__all__ = [
    "__version__",
    "ScenarioConfig",
    "ExperimentConfig",
    "ExperimentType",
    "run_experiment",
]

