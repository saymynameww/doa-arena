"""角度网格工具。"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class AngleGrid:
    """角度网格定义。

    Attributes:
        start: 起始角度（度）
        stop: 终止角度（度）
        step: 步长（度）
    """

    start: float
    stop: float
    step: float

    def __post_init__(self) -> None:
        """验证参数。"""
        if self.step <= 0:
            raise ValueError(f"步长必须大于 0，实际为 {self.step}")
        if self.start >= self.stop:
            raise ValueError(f"起始角度必须小于终止角度，实际为 {self.start} >= {self.stop}")

    @property
    def num_points(self) -> int:
        """网格点数。"""
        return int(np.ceil((self.stop - self.start) / self.step)) + 1

    def to_array(self) -> np.ndarray:
        """生成网格数组。

        Returns:
            角度数组，形状 (G,)
        """
        return np.arange(self.start, self.stop + self.step / 2, self.step)

    @classmethod
    def from_params(
        cls,
        start: float,
        stop: float,
        step: float,
    ) -> AngleGrid:
        """从参数创建网格。"""
        return cls(start=start, stop=stop, step=step)

    @classmethod
    def symmetric(cls, half_range: float, step: float) -> AngleGrid:
        """创建中心对称网格。

        Args:
            half_range: 半范围（度），如 60 表示 [-60, 60]
            step: 步长（度）

        Returns:
            AngleGrid 实例
        """
        return cls(start=-half_range, stop=half_range, step=step)
