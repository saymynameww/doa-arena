"""场景配置模型（简化版）。

完整版本将包含所有字段，这里先实现基础部分用于测试。
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class ArrayConfig(BaseModel):
    """阵列配置（简化版）。"""

    type: str = Field("ula", description="阵列类型")
    carrier_hz: float = Field(3e9, gt=0, description="载频（Hz，仅用于物理间距显示，不影响仿真）")
    params: dict[str, Any] = Field(
        default_factory=lambda: {"M": 16, "d": 0.5},
        description="阵列参数",
    )


class AnglesConfig(BaseModel):
    """角度配置（简化版）。"""

    mode: Literal["fixed", "random", "separation"] = Field(
        "fixed",
        description="角度生成模式",
    )
    values: list[float] | None = Field(
        [-10.0, 10.0],
        description="固定角度（mode=fixed）",
    )
    range_deg: tuple[float, float] | None = Field(
        None,
        description="随机范围（mode=random）",
    )
    center: float = Field(0, gt=-90, lt=90, description="角度中心（度）")
    min_separation: float = Field(0, ge=0, description="最小角度间隔（度）")
    delta: float | None = Field(
        None,
        description="角度间隔（mode=separation）",
    )

    @model_validator(mode="before")
    @classmethod
    def read_bounds(cls, data: Any) -> Any:
        """接受数据格式规范的 min/max，并兼容既有 range_deg 配置。"""
        if isinstance(data, dict) and data.get("mode") == "random":
            data = dict(data)
            if "range_deg" not in data:
                data["range_deg"] = (data.pop("min", -60), data.pop("max", 60))
            data.setdefault("min_separation", 2.0)
        return data


class CorrelationConfig(BaseModel):
    """信源相关性配置（简化版）。"""

    mode: Literal["none", "partial", "coherent"] = Field(
        "none",
        description="相关性模式",
    )
    rho_mag: float | None = Field(
        None,
        ge=0,
        lt=1,
        description="相关系数幅度（mode=partial）",
    )
    rho_phase_deg: float = Field(0, description="部分相关系数相位（度）")
    phases_deg: Literal["random"] | list[float] = Field(
        "random",
        description="相干相位（mode=coherent）",
    )

    @model_validator(mode="before")
    @classmethod
    def read_complex_rho(cls, data: Any) -> Any:
        """读取规范中的复相关系数。"""
        if isinstance(data, dict) and "rho" in data:
            data = dict(data)
            rho = data.pop("rho")
            data["rho_mag"] = rho["mag"]
            data["rho_phase_deg"] = rho.get("phase_deg", 0)
        return data


class RandomSourceCount(BaseModel):
    """随机信源数的离散取值。"""

    values: list[int] = Field(
        default_factory=lambda: [1, 2, 3], min_length=1, description="信源数取值集合"
    )
    weights: list[float] | None = None

    @model_validator(mode="before")
    @classmethod
    def read_distribution(cls, data: Any) -> Any:
        """解析离散分布，并拒绝会被静默忽略的错误写法。"""
        if not isinstance(data, dict):
            return data
        data = dict(data)
        if "choice" in data:
            data["values"] = data.pop("choice")
        if "uniform_int" in data:
            low, high = data.pop("uniform_int")
            if not isinstance(low, int) or not isinstance(high, int) or not 1 <= low <= high:
                raise ValueError("随机信源数范围必须为正整数，且下限不大于上限")
            data["values"] = list(range(low, high + 1))
        values = data.get("values", [1, 2, 3])
        weights = data.get("weights")
        if weights is not None and (
            len(weights) != len(values) or any(w < 0 for w in weights) or sum(weights) <= 0
        ):
            raise ValueError("权重数量必须等于取值数量，权重非负且总和大于零")
        return data


class SourcesConfig(BaseModel):
    """信源配置（简化版）。"""

    K: int | RandomSourceCount = Field(2, description="信源数")
    signal: Literal["gaussian"] = "gaussian"
    angles: AnglesConfig = Field(default_factory=lambda: AnglesConfig.model_validate({}))
    snr_db: float | list[float] = Field(10.0, description="信噪比（dB）")
    correlation: CorrelationConfig = Field(
        default_factory=lambda: CorrelationConfig.model_validate({})
    )


class ImpairmentConfig(BaseModel):
    """误差配置（简化版）。"""

    type: str = Field(..., description="误差插件 id")
    label: str | None = Field(None, description="显示名称")
    enabled: bool = Field(True, description="是否启用")
    realization: Literal["fixed", "per_trial"] = Field(
        "fixed",
        description="实现方式",
    )
    params: dict[str, Any] = Field(default_factory=dict)

    def get_label(self) -> str:
        """获取显示名称。"""
        return self.label if self.label is not None else self.type


class ScenarioConfig(BaseModel):
    """场景配置（简化版）。

    完整版本包含：
    - seed, name, description
    - sources (完整的角度、SNR、相关性配置)
    - array (完整的阵列配置)
    - impairments (误差列表)
    - snapshots, noise_power
    """

    seed: int = Field(42, ge=0, lt=2**63, description="随机种子")
    array: ArrayConfig = Field(default_factory=lambda: ArrayConfig.model_validate({}))
    sources: SourcesConfig = Field(default_factory=lambda: SourcesConfig.model_validate({}))
    snapshots: int = Field(100, ge=1, le=10000, description="快拍数")
    noise_power: float = Field(1.0, gt=0, description="噪声功率")
    noise: Literal["white_gaussian"] = "white_gaussian"
    impairments: list[ImpairmentConfig] = Field(
        default_factory=list,
        description="误差列表",
    )

    model_config = {
        "extra": "forbid",  # 禁止额外字段
    }

    @model_validator(mode="before")
    @classmethod
    def read_carrier(cls, data: Any) -> Any:
        """将载频显示字段映射到旧版界面使用的阵列配置。"""
        if isinstance(data, dict) and "carrier_hz" in data:
            data = dict(data)
            carrier = data.pop("carrier_hz")
            if carrier is not None:
                data["array"] = {**data.get("array", {}), "carrier_hz": carrier}
        return data
