"""接口规范 9.1–9.2 节：一个扫描点、一个算法的指标输入输出。"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from .types import Spectrum


@dataclass(frozen=True)
class MatchedSet:
    """全部试验的匹配结果；未运行试验已由框架排除。"""

    truth: np.ndarray
    K: np.ndarray
    estimates: np.ndarray
    K_hat: np.ndarray
    matched: np.ndarray
    error: np.ndarray
    failed: np.ndarray
    time_ms: np.ndarray
    spectra: Sequence[Spectrum | None] | None = None
    extra: Mapping[str, np.ndarray] = field(default_factory=dict)
    context: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MetricValue:
    """指标汇总值、逐源值、有效次数和附加统计量。"""

    value: float
    per_source: np.ndarray | None = None
    n_used: int | None = None
    extra: Mapping[str, float] = field(default_factory=dict)
