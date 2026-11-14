"""实验配置模型。

简化版，用于 M2 基础功能实现。
完整版本将在后续补充。
"""

from .experiment import ExperimentConfig, ExperimentType
from .scenario import ScenarioConfig

__all__ = [
    "ScenarioConfig",
    "ExperimentConfig",
    "ExperimentType",
]
