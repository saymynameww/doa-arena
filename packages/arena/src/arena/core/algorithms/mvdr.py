"""MVDR（Capon）算法插件。

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


class MVDR(Algorithm):
    """MVDR（Minimum Variance Distortionless Response / Capon）。

    最小方差无畸变响应波束形成。
    """

    id: ClassVar[str] = "mvdr"
    name: ClassVar[str] = "MVDR (Capon)"
    version: ClassVar[str] = "1.0.0"
    category: ClassVar[str] = "beamforming"
    description: ClassVar[str] = "最小方差无畸变响应，分辨率优于 CBF"

    capabilities: ClassVar[Capabilities] = Capabilities(
        needs_K=False,
        coherent="yes",
        batch=False,
        parallel=True,
        uses_gpu=False,
    )

    class Params(ParamsModel):
        """MVDR 参数。"""

        grid_start: float = Param(-90, label="搜索起始角度", unit="°")
        grid_stop: float = Param(90, label="搜索终止角度", unit="°")
        grid_step: float = Param(0.1, gt=0, label="网格步长", unit="°")
        diagonal_loading: float = Param(
            1e-6,
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

        ctx.log.info(f"MVDR 配置完成：网格共 {len(self.grid)} 点")

    def estimate(self, obs: Observation, ctx: RunContext) -> Estimate:
        """估计角度。"""
        if self.params is None or self.grid is None or self.A_grid is None:
            raise RuntimeError("MVDR 未配置")

        # 协方差
        R = obs.covariance()

        # 对角加载
        if self.params.diagonal_loading > 0:
            R = R + self.params.diagonal_loading * np.eye(obs.M)

        # R 逆
        try:
            R_inv = np.linalg.inv(R)
        except np.linalg.LinAlgError:
            # 奇异矩阵，增大对角加载
            ctx.log.warning("协方差矩阵奇异，增大对角加载")
            R = R + 1e-3 * np.eye(obs.M)
            R_inv = np.linalg.inv(R)

        # MVDR 谱：P(θ) = 1 / (a^H · R^{-1} · a)
        spectrum = np.zeros(len(self.grid))
        for i in range(len(self.grid)):
            a = self.A_grid[:, i : i + 1]  # (M, 1)
            denominator = (a.conj().T @ R_inv @ a).real[0, 0]
            spectrum[i] = 1.0 / (denominator + 1e-10)

        # 归一化
        spectrum /= spectrum.max()

        # 峰值搜索
        if obs.K is not None:
            K = obs.K
        else:
            K = min(3, len(self.grid) // 20)

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
