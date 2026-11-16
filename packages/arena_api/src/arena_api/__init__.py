"""DOA算法竞技场接口包。

外部算法只需要依赖这个包。
"""

__version__ = "1.0.0"

# 核心数据类型
# 工具箱（算法公共函数）
from . import kit

# 能力声明
from .capabilities import Capabilities

# 异常
from .errors import (
    ArenaError,
    ConfigError,
    PluginError,
    ValidationError,
)

# 角度网格
from .grid import AngleGrid

# 指标相关
from .metrics import (
    MatchedSet,
    MetricValue,
)

# 模型元数据
from .model import ModelMeta

# 参数声明
from .params import (
    ComplexValue,
    ModelPath,
    Param,
    ParamsModel,
)

# 插件基类
from .plugin import (
    Algorithm,
    AlgorithmSpec,
    ArrayModel,
    Impairment,
    Metric,
    ModelAlgorithm,
)
from .types import (
    ArrayDescriptor,
    Estimate,
    Observation,
    RunContext,
    Spectrum,
)

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
