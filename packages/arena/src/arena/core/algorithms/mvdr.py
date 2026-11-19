"""MVDR（Capon）算法插件。

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
    SpectrumSearchParams,
    kit,
)


class MVDR(Algorithm):
    """MVDR（Minimum Variance Distortionless Response / Capon）。

    最小方差无畸变响应波束形成。
    """

    id: ClassVar[str] = "mvdr"
    name: ClassVar[str] = "MVDR (Capon)"
    version: ClassVar[str] = "1.1.0"
    category: ClassVar[str] = "beamforming"
    description: ClassVar[str] = "最小方差无畸变响应，分辨率优于 CBF"

    capabilities: ClassVar[Capabilities] = Capabilities(
        needs_K=False,
        coherent="no",
        batch=False,
        parallel=True,
        uses_gpu=False,
    )

    class Params(SpectrumSearchParams):
        """MVDR 参数。"""

        peak_mode: Literal["top_k", "threshold"] = Param("top_k", label="取峰方式")
        peak_threshold_db: float = Param(10, ge=0, label="峰值门限", unit="dB")
        loading: float = Param(
            0.0,
            ge=0,
            label="对角加载",
            description="避免矩阵奇异，加到 R 的对角线上",
        )

    def __init__(self) -> None:
        super().__init__()
        self.params: MVDR.Params | None = None
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
        self.grid = kit.search_grid(
            params.scan_min, params.scan_max, params.grid_step, params.legacy_grid
        )
        self.array = array

        # 导向矢量
        self.element_mask = array.element_mask
        self.A_grid = array.steering(self.grid)[self.element_mask]

        ctx.log.info(f"MVDR 配置完成：网格共 {len(self.grid)} 点")

    def estimate(self, obs: Observation, ctx: RunContext) -> Estimate:
        """估计角度。"""
        if self.params is None or self.grid is None or self.A_grid is None:
            raise RuntimeError("MVDR 未配置")

        if not np.all(self.element_mask):
            obs = Observation(X=obs.X[self.element_mask], K=obs.K)

        # 协方差
        R = obs.covariance()

        R = R + self.params.loading * np.trace(R).real / obs.M * np.eye(obs.M)
        singular = np.linalg.matrix_rank(R) < obs.M
        R_inv = np.linalg.pinv(R) if singular else np.linalg.inv(R)
        denominator = np.real(np.sum(self.A_grid.conj() * (R_inv @ self.A_grid), axis=0))
        spectrum = 1 / np.maximum(denominator, np.finfo(float).tiny)

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

        def evaluate(angles: np.ndarray) -> np.ndarray:
            steering = self.array.steering(angles)[self.element_mask]
            values = np.real(np.sum(steering.conj() * (R_inv @ steering), axis=0))
            return 1 / np.maximum(values, np.finfo(float).tiny)

        peak_angles = kit.refine_spectrum_peaks(
            spectrum,
            self.grid,
            peak_angles,
            self.params.peak_refinement,
            evaluate,
            self.params.local_step,
        )

        return Estimate(
            angles=peak_angles,
            info={
                "used_pinv": bool(singular),
                "n_peaks_found": len(peak_angles),
                "peak_refinement": self.params.peak_refinement,
                "search_grid": [self.params.scan_min, self.params.scan_max, self.params.grid_step],
            },
            spectrum=Spectrum(
                grid=self.grid,
                values=spectrum,
                kind="power",
            )
            if ctx.want_spectrum
            else None,
        )
