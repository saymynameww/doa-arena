"""ESPRIT 算法插件。

按接口规范第 13.4 节实现，仅适用于 ULA。
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


class ESPRIT(Algorithm):
    """ESPRIT（Estimation of Signal Parameters via Rotational Invariance Techniques）算法。

    利用阵列的旋转不变性，仅适用于 ULA。
    """

    id: ClassVar[str] = "esprit"
    name: ClassVar[str] = "ESPRIT"
    version: ClassVar[str] = "1.0.0"
    category: ClassVar[str] = "subspace"
    description: ClassVar[str] = "利用旋转不变性的子空间算法，无需谱搜索"

    capabilities: ClassVar[Capabilities] = Capabilities(
        requires_ula=True,
        needs_K=True,
        coherent="with_smoothing",
        batch=False,
        parallel=True,
        uses_gpu=False,
    )

    class Params(ParamsModel):
        """ESPRIT 参数。"""

        method: Literal["ls", "tls"] = Param(
            "tls",
            label="求解方法",
            description="LS=最小二乘, TLS=总体最小二乘",
        )
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
        self.params: ESPRIT.Params | None = None
        self.d: float | None = None

    def configure(
        self,
        params: Params,
        array: ArrayDescriptor,
        ctx: RunContext,
    ) -> None:
        """配置算法。"""
        self.params = params
        self.d = array.ula_spacing

        if self.d is None:
            raise ValueError("ESPRIT 只能用于均匀线阵")

        ctx.log.info(f"ESPRIT 配置完成：method={params.method}, d={self.d}λ")

    def estimate(self, obs: Observation, ctx: RunContext) -> Estimate:
        """估计角度。"""
        if self.params is None or self.d is None:
            raise RuntimeError("ESPRIT 未配置")

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

        # ESPRIT
        angles = kit.esprit(R, obs.K, d=self.d, method=self.params.method)

        return Estimate(
            angles=angles,
            info={
                "method": self.params.method,
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
