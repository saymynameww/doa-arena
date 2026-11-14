"""算法能力声明。"""

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class Capabilities:
    """算法能力声明（静态类属性）。

    用于：
    1. 前端置灰不适用的算法
    2. 框架决定调用方式（批量、并行、GPU）

    Attributes:
        array_types: 支持的阵列插件 id 列表；None 表示任意阵列
        requires_ula: 是否需要 ULA（ArrayDescriptor.ula_spacing 非 None）
        supports_masked_elements: 能否处理 element_mask 中的 False（故障阵元）
        needs_K: 是否需要已知信源数
        coherent: 相干信源支持："yes" | "no" | "with_smoothing"
        batch: 是否支持批量估计（estimate_batch 方法）
        parallel: 是否可在多进程中并行（共享只读数据）
        uses_gpu: 是否使用 GPU
        dims: 支持的角度维数，V1 均为 (1,) 表示一维
    """

    # 阵列兼容性
    array_types: tuple[str, ...] | None = None
    requires_ula: bool = False
    supports_masked_elements: bool = True

    # 信源相关
    needs_K: bool = True
    coherent: Literal["yes", "no", "with_smoothing"] = "yes"

    # 执行方式
    batch: bool = False
    parallel: bool = True
    uses_gpu: bool = False

    # 角度维数（V1 只有一维）
    dims: tuple[int, ...] = (1,)
