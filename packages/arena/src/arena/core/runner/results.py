"""运行结果数据结构。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
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

    truth_angles: Any = None
    observation: np.ndarray | None = None
    source_count: int | None = None
    error_details: dict[str, dict[str, str]] = field(default_factory=dict)


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
    saved_summary: dict[str, Any] | None = None

    def to_latex_table(self, metric: str, path: str | Path, *, bold_best: bool = False) -> None:
        """将指定指标写成可直接插入论文的 booktabs 表格。"""
        from ..export.latex import export_to_latex

        export_to_latex(self, path, metric=metric, bold_best=bold_best)
