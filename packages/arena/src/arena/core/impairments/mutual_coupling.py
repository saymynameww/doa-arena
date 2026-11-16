"""互耦误差插件。

阵元间的互耦效应，使用对称 Toeplitz 矩阵建模。
"""

from collections.abc import Mapping
from typing import ClassVar, Literal

import numpy as np

from arena_api import ComplexValue, Impairment, Param, ParamsModel


class MutualCoupling(Impairment):
    """互耦误差。

    使用对称 Toeplitz 互耦矩阵 C 建模阵元间的互耦效应。
    """

    id: ClassVar[str] = "mutual_coupling"
    name: ClassVar[str] = "互耦"
    version: ClassVar[str] = "1.0.0"
    stage: ClassVar[Literal["manifold"]] = "manifold"

    class Params(ParamsModel):
        """互耦参数。"""

        coefficients: list[ComplexValue] = Param(
            [
                ComplexValue(magnitude=0.3, phase_deg=30),
                ComplexValue(magnitude=0.1, phase_deg=-20),
            ],
            label="互耦系数",
            description="c₁, c₂, ..., c_P（主对角线为 1，第 k 条对角线为 c_k）",
        )
        scale: float = Param(
            1.0,
            ge=0,
            le=10,
            label="强度因子",
            description="所有系数的幅度乘以此因子，用于扫描互耦强度",
        )

    def sample(
        self,
        rng: np.random.Generator,
        M: int,
    ) -> Mapping[str, np.ndarray]:
        """抽取标准化随机量。

        互耦是确定性的，返回空字典。

        Args:
            rng: 随机数生成器（未使用）
            M: 阵元数（未使用）

        Returns:
            空字典
        """
        return {}

    def apply(
        self,
        data: np.ndarray,
        draw: Mapping[str, np.ndarray],
        params: ParamsModel,
    ) -> np.ndarray:
        """应用互耦误差。

        Args:
            data: 真实流形 A，形状 (M, K)
            draw: 标准化随机量（空）
            params: 参数

        Returns:
            修改后的流形 C·A，形状 (M, K)
        """
        params = self.Params.model_validate(params)
        M, _K = data.shape

        # 构造对称 Toeplitz 互耦矩阵
        C = self._build_coupling_matrix(M, params)

        # C · A
        return C @ data

    def _build_coupling_matrix(self, M: int, params: Params) -> np.ndarray:
        """构造互耦矩阵。

        Args:
            M: 阵元数
            params: 参数

        Returns:
            互耦矩阵 C，形状 (M, M)
        """
        # 主对角线为 1
        C = np.eye(M, dtype=complex)

        # 系数转为复数并缩放
        coeffs = [
            cv.magnitude * params.scale * np.exp(1j * np.deg2rad(cv.phase_deg))
            for cv in params.coefficients
        ]

        # 填充 Toeplitz 矩阵
        for k, c_k in enumerate(coeffs, start=1):
            # 第 k 条对角线（主对角线上下各一条）
            for i in range(M - k):
                C[i, i + k] = c_k
                C[i + k, i] = c_k  # 对称

        return C

    def describe(
        self,
        draw: Mapping[str, np.ndarray],
        params: ParamsModel,
        M: int,
    ) -> Mapping[str, np.ndarray]:
        """描述互耦矩阵。

        Args:
            draw: 误差实现（空）
            params: 参数
            M: 阵元数

        Returns:
            互耦矩阵 "coupling_matrix" (M, M)
        """
        params = self.Params.model_validate(params)
        C = self._build_coupling_matrix(M, params)

        return {"coupling_matrix": C}
