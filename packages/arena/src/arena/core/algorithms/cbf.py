"""CBF（常规波束形成/Bartlett）算法插件。

按接口规范第 13.1 节实现。
"""

from typing import ClassVar

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
    Spectrum,
    kit,
)


class CBF(Algorithm):
    """常规波束形成（Conventional Beamforming / Bartlett）。

    最简单的波束形成方法，功率谱估计。
    """

    id: ClassVar[str] = "cbf"
    name: ClassVar[str] = "CBF (Bartlett)"
    version: ClassVar[str] = "1.0.0"
    category: ClassVar[str] = "beamforming"
    description: ClassVar[str] = "常规波束形成，基于功率谱的最简单方法"

    capabilities: ClassVar[Capabilities] = Capabilities(
        needs_K=False,  # 可以不需要 K（用门限取峰）
        coherent="yes",
        batch=False,
        parallel=True,
        uses_gpu=False,
    )

    class Params(ParamsModel):
        """CBF 参数。"""

        grid_start: float = Param(-90, label="搜索起始角度", unit="°")
        grid_stop: float = Param(90, label="搜索终止角度", unit="°")
        grid_step: float = Param(0.1, gt=0, label="网格步长", unit="°")

    def __init__(self) -> None:
        super().__init__()
        self.params: CBF.Params | None = None
        self.grid: np.ndarray | None = None
        self.A_grid: np.ndarray | None = None

    def configure(
        self,
        params: Params,
        array: ArrayDescriptor,
        ctx: RunContext,
    ) -> None:
        """配置算法。"""
        self.params = params

        # 角度网格
        self.grid = np.arange(
            params.grid_start,
            params.grid_stop + params.grid_step / 2,
            params.grid_step,
        )

        # 导向矢量
        self.A_grid = array.steering(self.grid)

        ctx.log.info(f"CBF 配置完成：网格共 {len(self.grid)} 点")

    def estimate(self, obs: Observation, ctx: RunContext) -> Estimate:
        """估计角度。"""
        if self.params is None or self.grid is None or self.A_grid is None:
            raise RuntimeError("CBF 未配置")

        # 协方差
        R = obs.covariance()

        # Bartlett 功率谱：P(θ) = a^H · R · a
        spectrum = np.zeros(len(self.grid))
        for i in range(len(self.grid)):
            a = self.A_grid[:, i : i + 1]  # (M, 1)
            spectrum[i] = (a.conj().T @ R @ a).real[0, 0]

        # 归一化
        spectrum /= spectrum.max()

        # 峰值搜索
        if obs.K is not None:
            K = obs.K
        else:
            # 没有 K 时，使用门限取峰（简化版）
            K = min(3, len(self.grid) // 20)  # 最多取 3 个峰

        peak_angles, _ = kit.peak_search(
            spectrum,
            self.grid,
            K=K,
            min_separation=self.params.grid_step * 0.5,
        )

        return Estimate(
            angles=peak_angles,
            spectrum=Spectrum(
                grid=self.grid,
                values=spectrum,
                kind="power",
            ) if ctx.want_spectrum else None,
        )
