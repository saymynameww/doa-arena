"""参数声明工具，基于 Pydantic。"""

from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, model_validator


class ParamsModel(BaseModel):
    """参数模型基类。

    所有插件的 Params 类都应继承此类。
    """

    model_config = {
        "extra": "forbid",  # 禁止额外字段
        "validate_assignment": True,  # 验证赋值
    }

    @model_validator(mode="before")
    @classmethod
    def migrate_legacy_names(cls, value: Any) -> Any:
        """读取旧版参数名，输出仍使用接口规范的正式名称。"""
        if isinstance(value, dict):
            value = dict(value)
            for old, new in {
                "grid_start": "scan_min",
                "grid_stop": "scan_max",
                "subarray_size": "subarray",
                "diagonal_loading": "loading",
            }.items():
                if old in value and new in cls.model_fields:
                    value.setdefault(new, value.pop(old))
        return value


def Param(
    default: Any = ...,
    *,
    gt: float | None = None,
    ge: float | None = None,
    lt: float | None = None,
    le: float | None = None,
    label: str | None = None,
    unit: str | None = None,
    description: str | None = None,
    none_label: str | None = None,
    **kwargs: Any,
) -> Any:
    """参数字段声明（Pydantic Field 的包装）。

    Args:
        default: 默认值
        gt: 大于（>）
        ge: 大于等于（>=）
        lt: 小于（<）
        le: 小于等于（<=）
        label: 前端显示标签（中文）
        unit: 单位（如 "°"、"Hz"）
        description: 详细说明
        none_label: None 值的显示文本（如 "自动"）
        **kwargs: 其他 Pydantic Field 参数

    Returns:
        Pydantic Field

    Example:
        >>> class MyParams(ParamsModel):
        ...     grid_step: float = Param(0.1, gt=0, le=5, label="网格步长", unit="°")
        ...     threshold: float | None = Param(None, ge=0, none_label="自动")
    """
    # 构建 json_schema_extra
    json_schema_extra = kwargs.pop("json_schema_extra", {})
    if label is not None:
        json_schema_extra["label"] = label
    if unit is not None:
        json_schema_extra["unit"] = unit
    if none_label is not None:
        json_schema_extra["none_label"] = none_label

    return Field(
        default=default,
        gt=gt,
        ge=ge,
        lt=lt,
        le=le,
        description=description,
        json_schema_extra=json_schema_extra,
        **kwargs,
    )


class SpectrumSearchParams(ParamsModel):
    """谱搜索基线的显式数值策略；旧 refine 仅作输入兼容。"""

    model_config = {"json_schema_extra": {"x-shared-grid": True}}
    grid_mode: Literal["shared", "custom"] = Param(
        "shared",
        label="网格来源",
        json_schema_extra={
            "x-summary": True,
            "x-enum-labels": {"shared": "实验统一网格", "custom": "独立网格（对比变体）"},
        },
    )
    scan_min: float = Param(
        -90,
        ge=-90,
        le=90,
        label="搜索起始角度",
        unit="°",
        json_schema_extra={"x-summary": True, "x-visible-when": {"grid_mode": "custom"}},
    )
    scan_max: float = Param(
        90,
        ge=-90,
        le=90,
        label="搜索终止角度",
        unit="°",
        json_schema_extra={"x-summary": True, "x-visible-when": {"grid_mode": "custom"}},
    )
    grid_step: float = Param(
        0.1,
        gt=0,
        le=5,
        label="网格步长",
        unit="°",
        json_schema_extra={"x-summary": True, "x-visible-when": {"grid_mode": "custom"}},
    )
    peak_refinement: Literal["none", "parabolic", "local_dense"] = Param(
        "none",
        label="寻峰策略",
        json_schema_extra={
            "x-summary": True,
            "x-enum-labels": {
                "none": "固定网格（无细化）",
                "parabolic": "三点抛物线插值",
                "local_dense": "局部逐级加密",
            },
        },
    )
    local_step: float = Param(
        0.0001,
        gt=0,
        label="局部终止步长",
        unit="°",
        json_schema_extra={
            "x-summary": True,
            "x-step": 0.0001,
            "x-visible-when": {"peak_refinement": "local_dense"},
        },
    )
    legacy_grid: bool = Param(False, json_schema_extra={"x-hidden": True})

    @model_validator(mode="before")
    @classmethod
    def read_refinement(cls, data: Any) -> Any:
        """显式旧布尔值保留含义；显式网格参数默认为独立网格。"""
        if not isinstance(data, dict):
            return data
        data = dict(data)
        if "refine" in data:
            value = data.pop("refine")
            if not isinstance(value, bool):
                raise ValueError("refine 必须是布尔值，请使用寻峰策略选择具体方式")
            mode = "parabolic" if value else "none"
            if "peak_refinement" in data and data["peak_refinement"] != mode:
                raise ValueError("refine 与寻峰策略冲突，请只保留一个一致的设置")
            data["peak_refinement"] = mode
        if "grid_mode" not in data and any(
            key in data for key in ("scan_min", "scan_max", "grid_step", "grid_start", "grid_stop")
        ):
            data["grid_mode"] = "custom"
        return data

    @model_validator(mode="after")
    def check_search(self) -> "SpectrumSearchParams":
        """拒绝不一致的数值配置，不静默改变步长。"""
        if self.scan_min >= self.scan_max:
            raise ValueError("搜索起始角度必须小于终止角度")
        if not self.legacy_grid:
            cells = (self.scan_max - self.scan_min) / self.grid_step
            if abs(cells - round(cells)) > 1e-7:
                raise ValueError("固定网格步长必须整除搜索范围，请调整步长或起止角度")
        if self.peak_refinement == "local_dense" and self.local_step > self.grid_step:
            raise ValueError("局部终止步长不能大于全局网格步长")
        return self


class ComplexValue(BaseModel):
    """复数值（用于配置文件）。

    Attributes:
        magnitude: 幅度
        phase_deg: 相位（度）
    """

    magnitude: float
    phase_deg: float = 0.0

    def to_complex(self) -> complex:
        """转换为 Python 复数。"""
        import numpy as np

        phase_rad = np.deg2rad(self.phase_deg)
        return self.magnitude * np.exp(1j * phase_rad)


# 接口规范 7.3：路径在配置中保持用户输入，界面根据标记提供选择器。
ModelPath = Annotated[str, Field(json_schema_extra={"x-widget": "model"})]
