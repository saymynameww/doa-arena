"""场景配置模型（简化版）。

完整版本将包含所有字段，这里先实现基础部分用于测试。
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ArrayConfig(BaseModel):
    """阵列配置（简化版）。"""

    type: str = Field("ula", description="阵列类型")
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
        None,
        description="固定角度（mode=fixed）",
    )
    range_deg: tuple[float, float] | None = Field(
        None,
        description="随机范围（mode=random）",
    )
    delta: float | None = Field(
        None,
        description="角度间隔（mode=separation）",
    )


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
    phases_deg: Literal["random"] | list[float] = Field(
        "random",
        description="相干相位（mode=coherent）",
    )


class SourcesConfig(BaseModel):
    """信源配置（简化版）。"""

    K: int = Field(2, ge=1, le=20, description="信源数")
    angles: AnglesConfig = Field(default_factory=AnglesConfig)
    snr_db: float = Field(10.0, description="信噪比（dB）")
    correlation: CorrelationConfig = Field(default_factory=CorrelationConfig)


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

    seed: int = Field(42, ge=0, lt=2**32, description="随机种子")
    array: ArrayConfig = Field(default_factory=ArrayConfig)
    sources: SourcesConfig = Field(default_factory=SourcesConfig)
    snapshots: int = Field(100, ge=1, le=10000, description="快拍数")
    noise_power: float = Field(1.0, gt=0, description="噪声功率")
    impairments: list[ImpairmentConfig] = Field(
        default_factory=list,
        description="误差列表",
    )

    model_config = {
        "extra": "forbid",  # 禁止额外字段
    }
