"""DOA算法竞技场接口包。

外部算法只需要依赖这个包。
"""

__version__ = "1.0.0"

# 核心数据类型
from .types import (
    ArrayDescriptor,
    Observation,
    Estimate,
    Spectrum,
    RunContext,
)

# 插件基类
from .plugin import (
    Algorithm,
    ModelAlgorithm,
    ArrayModel,
    Impairment,
    Metric,
    AlgorithmSpec,
)

# 参数声明
from .params import (
    ParamsModel,
    Param,
    ComplexValue,
    ModelPath,
)

# 能力声明
from .capabilities import Capabilities

# 指标相关
from .metrics import (
    MatchedSet,
    MetricValue,
)

# 模型元数据
from .model import ModelMeta

# 异常
from .errors import (
    ArenaError,
    PluginError,
    ConfigError,
    ValidationError,
)

# 角度网格
from .grid import AngleGrid

# 工具箱（算法公共函数）
from . import kit

__all__ = [
    "__version__",
    # Types
    "ArrayDescriptor",
    "Observation",
    "Estimate",
    "Spectrum",
    "RunContext",
    # Plugins
    "Algorithm",
    "ModelAlgorithm",
    "ArrayModel",
    "Impairment",
    "Metric",
    "AlgorithmSpec",
    # Params
    "ParamsModel",
    "Param",
    "ComplexValue",
    "ModelPath",
    # Capabilities
    "Capabilities",
    # Metrics
    "MatchedSet",
    "MetricValue",
    # Model
    "ModelMeta",
    # Errors
    "ArenaError",
    "PluginError",
    "ConfigError",
    "ValidationError",
    # Grid
    "AngleGrid",
    # Kit
    "kit",
]
