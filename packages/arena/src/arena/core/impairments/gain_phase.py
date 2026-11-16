"""幅相误差插件。

阵元增益和相位误差，参考阵元 g=1、φ=0。
"""

from collections.abc import Mapping
from typing import ClassVar, Literal

import numpy as np

from arena_api import Impairment, Param, ParamsModel


class GainPhase(Impairment):
    """幅相误差（增益和相位）。

    每个阵元的增益和相位独立偏离标称值，参考阵元固定。
    """

    id: ClassVar[str] = "gain_phase"
    name: ClassVar[str] = "幅相误差"
    version: ClassVar[str] = "1.0.0"
    stage: ClassVar[Literal["manifold"]] = "manifold"

    class Params(ParamsModel):
        """幅相误差参数。"""

        sigma_g: float = Param(
            0.05,
            ge=0,
            le=1.0,
            label="增益误差标准差",
            description="增益相对误差的标准差（线性值）",
        )
        sigma_phi_deg: float = Param(
            5.0,
            ge=0,
            le=180,
            label="相位误差标准差",
            unit="°",
            description="相位误差的标准差（度）",
        )
        fixed_gains: list[float] | None = Param(
            None,
            label="固定增益",
            none_label="随机",
            description="给定时忽略随机量，按给定值",
        )
        fixed_phases_deg: list[float] | None = Param(
            None,
            label="固定相位",
            unit="°",
            none_label="随机",
            description="给定时忽略随机量，按给定值（度）",
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
            标准化增益和相位误差（标准正态分布）
        """
        z_g = rng.normal(0, 1, M)
        z_phi = rng.normal(0, 1, M)

        # 参考阵元（第 0 个）误差为 0
        z_g[0] = 0.0
        z_phi[0] = 0.0

        return {"z_g": z_g, "z_phi": z_phi}

    def apply(
        self,
        data: np.ndarray,
        draw: Mapping[str, np.ndarray],
        params: Params,
    ) -> np.ndarray:
        """应用幅相误差。

        Args:
            data: 真实流形 A，形状 (M, K)
            draw: 标准化随机量
            params: 参数

        Returns:
            修改后的流形，形状 (M, K)
        """
        M, _K = data.shape

        # 计算实际增益和相位
        if params.fixed_gains is not None:
            # 使用固定增益
            gains = np.array(params.fixed_gains[:M])
            if len(gains) < M:
                raise ValueError(f"fixed_gains 长度 {len(gains)} 小于阵元数 {M}")
        else:
            # 随机增益：g = 1 + σ_g · z_g
            gains = 1.0 + params.sigma_g * draw["z_g"]

        if params.fixed_phases_deg is not None:
            # 使用固定相位（度）
            phases_deg = np.array(params.fixed_phases_deg[:M])
            if len(phases_deg) < M:
                raise ValueError(f"fixed_phases_deg 长度 {len(phases_deg)} 小于阵元数 {M}")
            phases_rad = np.deg2rad(phases_deg)
        else:
            # 随机相位：φ = σ_φ · z_φ
            phases_rad = np.deg2rad(params.sigma_phi_deg) * draw["z_phi"]

        # 幅相误差矩阵 Γ = diag(g · e^{jφ})
        gamma = gains * np.exp(1j * phases_rad)
        Gamma = np.diag(gamma)

        # Γ · A
        return Gamma @ data

    def describe(
        self,
        draw: Mapping[str, np.ndarray],
        params: Params,
        M: int,
    ) -> Mapping[str, np.ndarray]:
        """描述这次误差实现。

        Args:
            draw: 误差实现
            params: 参数
            M: 阵元数

        Returns:
            实际误差值字典，包含 "gain" (M,) 和 "phase_deg" (M,)
        """
        # 计算实际增益和相位
        if params.fixed_gains is not None:
            gains = np.array(params.fixed_gains[:M])
        else:
            gains = 1.0 + params.sigma_g * draw["z_g"]

        if params.fixed_phases_deg is not None:
            phases_deg = np.array(params.fixed_phases_deg[:M])
        else:
            phases_deg = params.sigma_phi_deg * draw["z_phi"]

        return {
            "gain": gains,
            "phase_deg": phases_deg,
        }
