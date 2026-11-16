"""实验配置模型（简化版）。"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from .scenario import ScenarioConfig


class ExperimentType(str, Enum):
    """实验类型。"""

    SINGLE = "single"
    MONTE_CARLO = "monte_carlo"
    SWEEP = "sweep"


class AlgorithmConfig(BaseModel):
    """算法配置（简化版）。"""

    id: str = Field(..., description="算法插件 id")
    label: str | None = Field(None, description="显示名称")
    enabled: bool = Field(True, description="是否启用")
    params: dict[str, Any] = Field(default_factory=dict)

    def get_label(self) -> str:
        """获取显示名称。"""
        return self.label if self.label is not None else self.id


class SweepConfig(BaseModel):
    """扫描配置（简化版）。"""

    path: str = Field(..., description="扫描变量路径")
    values: list[float] = Field(..., min_length=2, description="扫描取值")
    label: str | None = Field(None, description="横轴名称")
    unit: str | None = Field(None, description="单位")


class ExperimentOptions(BaseModel):
    """实验选项（简化版）。"""

    workers: int = Field(1, ge=1, le=64, description="并行进程数")
    common_random_numbers: bool = Field(True, description="公共随机数")
    warmup: bool = Field(True, description="是否预热")
    save_estimates: bool = Field(True, description="保存估计值")


class SuccessParameters(BaseModel):
    """成功判定参数，角度单位为度。"""

    threshold_deg: float = Field(1.0, gt=0, description="成功门限（度）")


class MetricParameters(BaseModel):
    """指标参数。"""

    success_rate: SuccessParameters = Field(
        default_factory=lambda: SuccessParameters(threshold_deg=1.0)
    )


class MetricsConfig(BaseModel):
    """数据格式 3.7 节的指标选择。"""

    include: list[str] = Field(
        default_factory=lambda: ["rmse", "success_rate", "resolution", "time", "crb"]
    )
    params: MetricParameters = Field(default_factory=MetricParameters)


class ExperimentConfig(BaseModel):
    """实验配置（简化版）。

    完整版本包含：
    - schema_version, name, description, created
    - scenario (完整配置)
    - algorithms (算法列表)
    - experiment (type, trials, sweep, options)
    - metrics (指标配置)
    """

    name: str = Field("Untitled Experiment", description="实验名称")
    scenario: ScenarioConfig = Field(default_factory=ScenarioConfig)
    algorithms: list[AlgorithmConfig] = Field(default_factory=list)

    # 实验类型
    type: ExperimentType = Field(ExperimentType.MONTE_CARLO)
    trials: int = Field(100, ge=1, le=1000000, description="试验次数")
    sweep: SweepConfig | None = Field(None, description="扫描配置")

    metrics: MetricsConfig = Field(default_factory=MetricsConfig)

    # 选项
    options: ExperimentOptions = Field(default_factory=ExperimentOptions)

    model_config = {
        "extra": "forbid",
        "use_enum_values": True,
    }

    def validate_experiment(self) -> None:
        """验证实验配置一致性。

        Raises:
            ValueError: 配置不一致
        """
        # single 实验必须 trials=1
        if self.type == ExperimentType.SINGLE and self.trials != 1:
            raise ValueError("single 实验必须设置 trials=1")

        # sweep 实验必须有 sweep 配置
        if self.type == ExperimentType.SWEEP and self.sweep is None:
            raise ValueError("sweep 实验必须提供 sweep 配置")

        # 至少一个算法
        if not any(algo.enabled for algo in self.algorithms):
            raise ValueError("至少需要一个算法")

        # 算法 label 唯一
        labels = [algo.get_label() for algo in self.algorithms if algo.enabled]
        if len(labels) != len(set(labels)):
            raise ValueError("算法 label 必须唯一")
