"""均匀线阵（ULA）插件。"""

from typing import ClassVar

import numpy as np
from arena_api import ArrayModel, Param, ParamsModel


class ULA(ArrayModel):
    """均匀线阵（Uniform Linear Array）。

    阵元沿 x 轴等间距排列，第 0 个阵元在原点。
    """

    id: ClassVar[str] = "ula"
    name: ClassVar[str] = "均匀线阵（ULA）"

    class Params(ParamsModel):
        """ULA 参数。"""

        M: int = Param(16, ge=2, le=128, label="阵元数")
        d: float = Param(0.5, gt=0, le=2, label="阵元间距", unit="λ")

    def positions(self, params: Params) -> np.ndarray:
        """计算阵元位置。

        Args:
            params: ULA 参数

        Returns:
            阵元位置，形状 (M, 3)，沿 x 轴
        """
        M = params.M
        d = params.d

        # 阵元位置：[0, d, 2d, ..., (M-1)d] 沿 x 轴
        x = np.arange(M) * d
        y = np.zeros(M)
        z = np.zeros(M)

        positions = np.column_stack([x, y, z])
        return positions

    def steering(
        self,
        angles: np.ndarray,
        positions: np.ndarray,
    ) -> np.ndarray:
        """计算导向矢量（使用默认实现）。

        默认实现已经正确，无需覆盖。
        """
        return super().steering(angles, positions)
