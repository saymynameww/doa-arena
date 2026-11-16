"""实验配置模型（简化版）。"""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, PrivateAttr, model_validator

from .scenario import ScenarioConfig


class ExperimentType(str, Enum):
    """实验类型。"""

    SINGLE = "single"
    MONTE_CARLO = "monte_carlo"
    SWEEP = "sweep"


class AlgorithmConfig(BaseModel):
    """算法配置（简化版）。"""

    id: str = Field(..., description="算法插件 id")
    origin: dict[str, Any] | None = None
    label: str | None = Field(None, description="显示名称")
    enabled: bool = Field(True, description="是否启用")
    params: dict[str, Any] = Field(default_factory=dict)

    def get_label(self) -> str:
        """获取显示名称。"""
        return self.label if self.label is not None else self.id


class SweepConfig(BaseModel):
    """扫描配置（简化版）。"""

    path: str = Field(..., description="扫描变量路径")
    values: list[float] = Field(..., min_length=2, max_length=200, description="扫描取值")
    label: str | None = Field(None, description="横轴名称")
    unit: str | None = Field(None, description="单位")


class ExperimentOptions(BaseModel):
    """实验选项（简化版）。"""

    chunk_size: int = Field(64, ge=1, le=10000)
    max_consecutive_errors: int = Field(20, ge=1)
    source_count: Literal["true", "mdl", "aic"] = "true"
    save_spectra: Literal["auto", "all", "none"] = "auto"
    save_observations: Literal["auto", "none"] = "auto"
    workers: int = Field(1, ge=1, le=64, description="并行进程数")
    common_random_numbers: bool = Field(True, description="公共随机数")
    warmup: bool = Field(True, description="是否预热")
    save_estimates: bool = Field(True, description="保存估计值")


class SuccessParameters(BaseModel):
    """成功判定参数，角度单位为度。"""

    threshold_deg: float = Field(1.0, gt=0, description="成功门限（度）")


class RmseParameters(BaseModel):
    """估计数错误时的 RMSE 纳入规则。"""

    include_failed: bool = False
    penalty_deg: float = Field(90, gt=0)


class MetricParameters(BaseModel):
    """指标参数。"""

    success_rate: SuccessParameters = Field(
        default_factory=lambda: SuccessParameters(threshold_deg=1.0)
    )
    rmse: RmseParameters = Field(default_factory=lambda: RmseParameters.model_validate({}))
    model_config = {"extra": "allow"}


class MetricsConfig(BaseModel):
    """数据格式 3.7 节的指标选择。"""

    include: list[str] = Field(
        default_factory=lambda: ["rmse", "success_rate", "resolution", "time", "crb"]
    )
    params: MetricParameters = Field(default_factory=MetricParameters)
    origins: dict[str, dict[str, Any]] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def read_crb_selection(cls, data: Any) -> Any:
        """兼容旧版将 CRB 放进 include 的配置，读取规范独立开关。"""
        if not isinstance(data, dict):
            return data
        data = dict(data)
        include = list(data.get("include", ["rmse", "success_rate", "resolution", "time"]))
        include = ["resolution" if item == "resolution_prob" else item for item in include]
        enabled = data.pop("crb", "crb" in include if "include" in data else True)
        include = [item for item in include if item != "crb"]
        data["include"] = [*include, "crb"] if enabled else include
        return data


class ExperimentConfig(BaseModel):
    """实验配置（简化版）。

    完整版本包含：
    - schema_version, name, description, created
    - scenario (完整配置)
    - algorithms (算法列表)
    - experiment (type, trials, sweep, options)
    - metrics (指标配置)
    """

    schema_version: Literal[1] = 1
    _workspace: Path | None = PrivateAttr(default=None)
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    name: str = Field("Untitled Experiment", min_length=1, max_length=80, description="实验名称")
    scenario: ScenarioConfig = Field(default_factory=lambda: ScenarioConfig.model_validate({}))
    algorithms: list[AlgorithmConfig] = Field(default_factory=list)

    # 实验类型
    type: ExperimentType = Field(ExperimentType.MONTE_CARLO)
    trials: int = Field(100, ge=1, le=1000000, description="试验次数")
    sweep: SweepConfig | None = Field(None, description="扫描配置")

    metrics: MetricsConfig = Field(default_factory=MetricsConfig)

    # 选项
    options: ExperimentOptions = Field(default_factory=lambda: ExperimentOptions.model_validate({}))

    model_config = {
        "extra": "forbid",
        "use_enum_values": True,
    }

    @model_validator(mode="before")
    @classmethod
    def read_document(cls, data: Any) -> Any:
        """读取规范的 experiment 层级，并保留旧前端草稿兼容性。"""
        if not isinstance(data, dict):
            return data
        data = dict(data)
        if "experiment" in data:
            experiment = data.pop("experiment")
            unknown = set(experiment) - {"type", "trials", "sweep", "options"}
            if unknown:
                raise ValueError(f"experiment 含未知字段：{sorted(unknown)}")
            data.update(experiment)
            if "seed" not in data and "seed" not in data.get("scenario", {}):
                import secrets

                data["seed"] = secrets.randbits(63)
        if "seed" in data:
            data["scenario"] = {**data.get("scenario", {}), "seed": data.pop("seed")}
        return data

    def to_document(self) -> dict[str, Any]:
        """生成数据格式规范第 3 章的配置文档。"""
        data = self.model_dump(mode="json")
        data["experiment"] = {key: data.pop(key) for key in ("type", "trials", "sweep", "options")}
        scenario = data["scenario"]
        data["seed"] = scenario.pop("seed")
        scenario["carrier_hz"] = scenario["array"].pop("carrier_hz")
        if scenario["noise_power"] == 1:
            scenario.pop("noise_power")
        sources = scenario["sources"]
        if isinstance(sources["K"], dict):
            sources["K"]["choice"] = sources["K"].pop("values")
        angles = sources["angles"]
        if angles["mode"] == "random" and angles.get("range_deg"):
            angles["min"], angles["max"] = angles.pop("range_deg")
        correlation = sources["correlation"]
        mag = correlation.pop("rho_mag")
        phase = correlation.pop("rho_phase_deg")
        if mag is not None:
            correlation["rho"] = {"mag": mag, "phase_deg": phase}
        metrics = data["metrics"]
        metrics["crb"] = "crb" in metrics["include"]
        metrics["include"] = [
            "resolution_prob" if item == "resolution" else item
            for item in metrics["include"]
            if item != "crb"
        ]
        return data

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
