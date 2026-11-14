"""参数声明工具，基于 Pydantic。"""

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class ParamsModel(BaseModel):
    """参数模型基类。

    所有插件的 Params 类都应继承此类。
    """

    model_config = {
        "extra": "forbid",  # 禁止额外字段
        "validate_assignment": True,  # 验证赋值
    }


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


class ModelPath(BaseModel):
    """模型文件路径（用于学习型算法参数）。

    Attributes:
        path: 模型文件路径
        device: 推理设备，"cpu" 或 "cuda"
    """

    path: Path
    device: str = "cpu"

    def validate_device(self) -> None:
        """验证设备可用性。"""
        if self.device == "cpu":
            return

        # 检查 CUDA
        if self.device.startswith("cuda"):
            try:
                import torch

                if not torch.cuda.is_available():
                    raise ValueError("CUDA 不可用")
            except ImportError:
                raise ValueError("PyTorch 未安装，无法使用 CUDA")
