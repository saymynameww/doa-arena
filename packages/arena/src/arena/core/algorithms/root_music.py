"""Root-MUSIC 算法插件。

按接口规范第 13.3 节实现，仅适用于 ULA。
"""

from typing import ClassVar, Literal

import numpy as np
from arena_api import (
    Algorithm,
    ArrayDescriptor,
    Capabilities,
    Estimate,
    Observation,
    Param,
    ParamsModel,
    RunContext,
    kit,
)


class RootMUSIC(Algorithm):
    """Root-MUSIC 算法。

    通过求根而非谱搜索估计角度，仅适用于 ULA。
    """

    id: ClassVar[str] = "root_music"
    name: ClassVar[str] = "Root-MUSIC"
    version: ClassVar[str] = "1.0.0"
    category: ClassVar[str] = "subspace"
    description: ClassVar[str] = "MUSIC 的求根版本，避免谱搜索，计算效率更高"

    capabilities: ClassVar[Capabilities] = Capabilities(
        requires_ula=True,
        needs_K=True,
        coherent="with_smoothing",
        batch=False,
        parallel=True,
        uses_gpu=False,
    )

    class Params(ParamsModel):
        """Root-MUSIC 参数。"""

        smoothing: Literal["none", "forward", "fb"] = Param(
            "none",
            label="空间平滑",
        )
        subarray_size: int | None = Param(
            None,
            ge=2,
            label="子阵阵元数",
            none_label="自动",
        )

    def __init__(self) -> None:
        super().__init__()
        self.params: RootMUSIC.Params | None = None
        self.d: float | None = None

    def configure(
        self,
        params: Params,
        array: ArrayDescriptor,
        ctx: RunContext,
    ) -> None:
        """配置算法。

        Args:
            params: 参数
            array: 阵列描述
            ctx: 运行上下文
        """
        self.params = params
        self.d = array.ula_spacing

        if self.d is None:
            raise ValueError("Root-MUSIC 只能用于均匀线阵")

        ctx.log.info(f"Root-MUSIC 配置完成：d={self.d}λ")

    def estimate(self, obs: Observation, ctx: RunContext) -> Estimate:
        """估计角度。

        Args:
            obs: 观测数据
            ctx: 运行上下文

        Returns:
            估计结果
        """
        if self.params is None or self.d is None:
            raise RuntimeError("Root-MUSIC 未配置")

        # 协方差
        R = obs.covariance()

        # 空间平滑
        if self.params.smoothing != "none":
            L = self._get_subarray_size(obs.M, obs.K)
            R = kit.spatial_smoothing(
                R,
                L=L,
                forward_backward=(self.params.smoothing == "fb"),
            )

        # Root-MUSIC
        angles = kit.root_music(R, obs.K, d=self.d)

        return Estimate(
            angles=angles,
            info={
                "smoothing": self.params.smoothing,
            },
        )

    def _get_subarray_size(self, M: int, K: int) -> int:
        """确定子阵大小。"""
        if self.params.subarray_size is not None:
            L = self.params.subarray_size
        else:
            L = int(np.ceil(2 * M / 3))

        if L > M:
            L = M
        if L <= K:
            L = K + 1

        return L
