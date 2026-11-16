"""位置误差插件。

阵元位置偏离标称位置，参考阵元（第 0 个）误差为 0。
"""

from collections.abc import Mapping
from typing import ClassVar, Literal

import numpy as np

from arena_api import Impairment, Param, ParamsModel


class PositionError(Impairment):
    """阵元位置误差。

    每个阵元在指定轴上独立偏离标称位置，参考阵元固定。
    """

    id: ClassVar[str] = "position"
    name: ClassVar[str] = "位置误差"
    version: ClassVar[str] = "1.0.0"
    stage: ClassVar[Literal["positions"]] = "positions"

    class Params(ParamsModel):
        """位置误差参数。"""

        sigma: float = Param(
            0.01,
            gt=0,
            le=1.0,
            label="位置误差标准差",
            unit="λ",
            description="各阵元在指定轴上的位置误差标准差",
        )
        axes: Literal["x", "xy", "xyz"] = Param(
            "x",
            label="误差方向",
            description="x=仅沿x轴, xy=xy平面, xyz=三维空间",
        )

    def sample(
        self,
        rng: np.random.Generator,
        M: int,
    ) -> Mapping[str, np.ndarray]:
        """抽取标准化随机量。

        Args:
            rng: 随机数生成器
            M: 阵元数

        Returns:
            标准化位置偏移（标准正态分布），形状 (M, 3)
        """
        # 标准正态分布
        z = rng.normal(0, 1, (M, 3))

        # 参考阵元（第 0 个）误差为 0
        z[0, :] = 0.0

        return {"z": z}

    def apply(
        self,
        data: np.ndarray,
        draw: Mapping[str, np.ndarray],
        params: ParamsModel,
    ) -> np.ndarray:
        """应用位置误差。

        Args:
            data: 标称位置，形状 (M, 3)
            draw: 标准化随机量
            params: 参数

        Returns:
            实际位置，形状 (M, 3)
        """
        params = self.Params.model_validate(params)
        positions = data.copy()
        z = draw["z"]

        # 根据 axes 选择生效的轴
        if params.axes == "x":
            offset = np.column_stack(
                [
                    params.sigma * z[:, 0],
                    np.zeros(len(z)),
                    np.zeros(len(z)),
                ]
            )
        elif params.axes == "xy":
            offset = np.column_stack(
                [
                    params.sigma * z[:, 0],
                    params.sigma * z[:, 1],
                    np.zeros(len(z)),
                ]
            )
        else:  # xyz
            offset = params.sigma * z

        return positions + offset

    def describe(
        self,
        draw: Mapping[str, np.ndarray],
        params: ParamsModel,
        M: int,
    ) -> Mapping[str, np.ndarray]:
        """描述这次误差实现。

        Args:
            draw: 误差实现
            params: 参数
            M: 阵元数

        Returns:
            实际误差值字典，包含 "offset" (M, 3)
        """
        params = self.Params.model_validate(params)
        z = draw["z"]

        # 计算实际偏移
        if params.axes == "x":
            offset = np.column_stack(
                [
                    params.sigma * z[:, 0],
                    np.zeros(M),
                    np.zeros(M),
                ]
            )
        elif params.axes == "xy":
            offset = np.column_stack(
                [
                    params.sigma * z[:, 0],
                    params.sigma * z[:, 1],
                    np.zeros(M),
                ]
            )
        else:  # xyz
            offset = params.sigma * z

        return {"offset": offset}
