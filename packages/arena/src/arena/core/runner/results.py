"""运行结果数据结构。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from arena_api import Estimate


@dataclass
class TrialResult:
    """单次试验结果。"""

    trial_idx: int
    estimates: dict[str, Estimate]  # 算法 label -> 估计结果
    errors: dict[str, str]  # 算法 label -> 错误信息
    times_ms: dict[str, float]  # 算法 label -> 耗时（毫秒）


@dataclass
class SweepPointResult:
    """扫描点结果。"""

    point_idx: int
    sweep_value: float | None
    trials: list[TrialResult]


@dataclass
class ExperimentResult:
    """实验结果。"""

    config: dict[str, Any]  # 实验配置
    points: list[SweepPointResult]  # 扫描点结果
    metadata: dict[str, Any]  # 元信息（开始时间、耗时等）
