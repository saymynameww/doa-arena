"""CBF（常规波束形成/Bartlett）算法插件。

按接口规范第 13.1 节实现。
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

        scan_min: float = Param(-90, label="搜索起始角度", unit="°")
        scan_max: float = Param(90, label="搜索终止角度", unit="°")
        grid_step: float = Param(0.1, gt=0, label="网格步长", unit="°")
        refine: bool = Param(True, label="抛物线峰值细化")
        peak_mode: Literal["top_k", "threshold"] = Param("top_k", label="取峰方式")
        peak_threshold_db: float = Param(10, ge=0, label="峰值门限", unit="dB")

    def __init__(self) -> None:
        super().__init__()
        self.params: CBF.Params | None = None
        self.grid: np.ndarray | None = None
        self.A_grid: np.ndarray | None = None

    def configure(
        self,
        params: ParamsModel,
        array: ArrayDescriptor,
        ctx: RunContext,
    ) -> None:
        """配置算法。"""
        params = self.Params.model_validate(params)
        self.params = params

        # 角度网格
        self.grid = np.arange(
            params.scan_min,
            params.scan_max + params.grid_step / 2,
            params.grid_step,
        )

        # 导向矢量
        self.element_mask = array.element_mask
        self.A_grid = array.steering(self.grid)[self.element_mask]

        ctx.log.info(f"CBF 配置完成：网格共 {len(self.grid)} 点")

    def estimate(self, obs: Observation, ctx: RunContext) -> Estimate:
        """估计角度。"""
        if self.params is None or self.grid is None or self.A_grid is None:
            raise RuntimeError("CBF 未配置")

        if not np.all(self.element_mask):
            obs = Observation(X=obs.X[self.element_mask], K=obs.K)

        # 协方差
        R = obs.covariance()

        # Bartlett 功率谱：P(θ) = a^H · R · a
        spectrum = np.real(np.sum(self.A_grid.conj() * (R @ self.A_grid), axis=0))
        spectrum /= np.sum(np.abs(self.A_grid) ** 2, axis=0)

        # 归一化
        spectrum /= spectrum.max()

        # 峰值搜索
        K = obs.K if self.params.peak_mode == "top_k" and obs.K is not None else len(self.grid)
        peak_angles, _ = kit.peak_search(
            spectrum,
            self.grid,
            K=K,
            min_separation=self.params.grid_step * 0.5,
        )

        if self.params.peak_mode == "threshold":
            peak_angles = peak_angles[
                np.interp(peak_angles, self.grid, spectrum)
                >= 10 ** (-self.params.peak_threshold_db / 10)
            ]
        if self.params.refine:
            peak_angles = kit.refine_peaks(spectrum, self.grid, peak_angles)

        return Estimate(
            angles=peak_angles,
            spectrum=Spectrum(
                grid=self.grid,
                values=spectrum,
                kind="power",
            )
            if ctx.want_spectrum
            else None,
        )
