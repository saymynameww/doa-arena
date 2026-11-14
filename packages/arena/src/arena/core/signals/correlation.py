"""信源相关性处理。

支持不相干、部分相关、相干三种模式。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np


@dataclass
class CorrelationMatrix:
    """信源协方差矩阵 P = E[s·s^H]。

    Attributes:
        mode: 相关性模式
        K: 信源数
        powers: 信源功率，形状 (K,)
        rho: 相关系数矩阵（部分相关模式）或相干系数（相干模式）
    """

    mode: Literal["independent", "partial", "coherent"]
    K: int
    powers: np.ndarray
    rho: np.ndarray | None = None

    def to_matrix(self) -> np.ndarray:
        """生成协方差矩阵 P。

        Returns:
            P 矩阵，形状 (K, K)
        """
        if self.mode == "independent":
            # 不相干：P = diag(σ_1², ..., σ_K²)
            return np.diag(self.powers)

        elif self.mode == "partial":
            # 部分相关：P_ij = ρ_ij · σ_i · σ_j
            if self.rho is None:
                raise ValueError("部分相关模式需要提供 rho")

            P = self.rho * np.outer(np.sqrt(self.powers), np.sqrt(self.powers))

            # 确保半正定（数值误差可能导致负特征值）
            eigvals = np.linalg.eigvalsh(P)
            if np.any(eigvals < -1e-10):
                raise ValueError(
                    f"相关系数矩阵不是半正定的，最小特征值为 {eigvals.min()}"
                )

            return P

        elif self.mode == "coherent":
            # 相干：s_k = α_k · s_1
            # P = α · α^H · σ_1²（秩为1）
            if self.rho is None:
                raise ValueError("相干模式需要提供相干系数 alpha")

            alpha = self.rho  # 相干系数向量，形状 (K,)
            # 归一化：alpha[0] = 1
            if not np.isclose(np.abs(alpha[0]), 1.0):
                alpha = alpha / alpha[0]

            # P = α · α^H · σ_1²
            P = np.outer(alpha, alpha.conj()) * self.powers[0]

            return P

        else:
            raise ValueError(f"未知的相关性模式：{self.mode}")

    @classmethod
    def independent(cls, powers: np.ndarray) -> CorrelationMatrix:
        """创建不相干配置。

        Args:
            powers: 信源功率，形状 (K,)

        Returns:
            CorrelationMatrix 实例
        """
        return cls(
            mode="independent",
            K=len(powers),
            powers=powers,
            rho=None,
        )

    @classmethod
    def partial_correlated(
        cls,
        powers: np.ndarray,
        rho_magnitude: float,
        rho_phase_deg: float = 0.0,
    ) -> CorrelationMatrix:
        """创建部分相关配置（所有信源两两相关系数相同）。

        Args:
            powers: 信源功率，形状 (K,)
            rho_magnitude: 相关系数幅度，[0, 1)
            rho_phase_deg: 相关系数相位（度）

        Returns:
            CorrelationMatrix 实例
        """
        K = len(powers)
        if not (0 <= rho_magnitude < 1):
            raise ValueError(f"相关系数幅度必须在 [0, 1) 范围内，实际为 {rho_magnitude}")

        # 检查半正定约束
        # 对于所有元素相同的相关系数矩阵：
        # 最小特征值约为 1 - (K-1)·|ρ|
        # 要求 >= 0，即 |ρ| <= 1/(K-1)
        if K > 1:
            max_rho = 1.0 / (K - 1)
            if rho_magnitude > max_rho:
                raise ValueError(
                    f"对于 K={K} 个信源，相关系数幅度不能超过 {max_rho:.4f}，"
                    f"实际为 {rho_magnitude}"
                )

        # 相关系数矩阵
        rho_complex = rho_magnitude * np.exp(1j * np.deg2rad(rho_phase_deg))
        rho_matrix = np.full((K, K), rho_complex, dtype=complex)
        np.fill_diagonal(rho_matrix, 1.0)

        return cls(
            mode="partial",
            K=K,
            powers=powers,
            rho=rho_matrix,
        )

    @classmethod
    def coherent(
        cls,
        powers: np.ndarray,
        alpha: np.ndarray | None = None,
    ) -> CorrelationMatrix:
        """创建相干配置。

        Args:
            powers: 信源功率，形状 (K,)
            alpha: 相干系数，形状 (K,)，默认按功率自动生成

        Returns:
            CorrelationMatrix 实例
        """
        K = len(powers)

        if alpha is None:
            # 默认：幅度按功率，相位随机（需要外部提供随机相位）
            # 这里先用全1，实际使用时需要传入
            alpha = np.ones(K, dtype=complex)
        else:
            alpha = np.asarray(alpha, dtype=complex)
            if len(alpha) != K:
                raise ValueError(f"alpha 长度必须为 {K}，实际为 {len(alpha)}")

        return cls(
            mode="coherent",
            K=K,
            powers=powers,
            rho=alpha,
        )


def generate_correlated_sources(
    corr_matrix: CorrelationMatrix,
    N: int,
    rng: np.random.Generator,
) -> np.ndarray:
    """生成相关信源。

    Args:
        corr_matrix: 相关性配置
        N: 快拍数
        rng: 随机数生成器

    Returns:
        信源矩阵，形状 (K, N)
    """
    K = corr_matrix.K
    P = corr_matrix.to_matrix()

    if corr_matrix.mode == "independent":
        # 不相干：直接生成独立信源
        real = rng.normal(0, 1, (K, N))
        imag = rng.normal(0, 1, (K, N))
        S = (real + 1j * imag) / np.sqrt(2)

        # 缩放到目标功率
        for k in range(K):
            S[k, :] *= np.sqrt(corr_matrix.powers[k])

        return S

    elif corr_matrix.mode == "coherent":
        # 相干：P 奇异（秩为1），用特征分解
        # P = U·Λ·U^H，只有一个非零特征值
        eigvals, eigvecs = np.linalg.eigh(P)

        # 降序排列
        idx = np.argsort(eigvals)[::-1]
        eigvals = eigvals[idx]
        eigvecs = eigvecs[:, idx]

        # 取最大特征值对应的特征向量
        λ_max = eigvals[0]
        u_max = eigvecs[:, 0]

        # 生成基础信号 s_1
        real = rng.normal(0, 1, N)
        imag = rng.normal(0, 1, N)
        s_base = (real + 1j * imag) / np.sqrt(2)
        s_base *= np.sqrt(λ_max)

        # S = u_max · s_base
        S = np.outer(u_max, s_base)

        return S

    else:
        # 部分相关：Cholesky 分解
        # P = L·L^H，S = L·S_0，其中 S_0 是独立的
        try:
            L = np.linalg.cholesky(P)
        except np.linalg.LinAlgError:
            # Cholesky 失败（数值问题），改用特征分解
            eigvals, eigvecs = np.linalg.eigh(P)
            eigvals = np.maximum(eigvals, 0)  # 负特征值置零
            L = eigvecs @ np.diag(np.sqrt(eigvals))

        # 生成独立的基础信号
        real = rng.normal(0, 1, (K, N))
        imag = rng.normal(0, 1, (K, N))
        S0 = (real + 1j * imag) / np.sqrt(2)

        # 应用相关性
        S = L @ S0

        return S


def validate_correlation_config(
    mode: str,
    K: int,
    rho: dict | None = None,
) -> None:
    """验证相关性配置合法性。

    Args:
        mode: 相关性模式
        K: 信源数
        rho: 相关系数配置

    Raises:
        ValueError: 配置不合法
    """
    if mode not in ["independent", "partial", "coherent"]:
        raise ValueError(f"未知的相关性模式：{mode}")

    if mode in ["partial", "coherent"] and rho is None:
        raise ValueError(f"{mode} 模式需要提供相关系数配置")

    if mode == "partial" and rho is not None:
        magnitude = rho.get("magnitude", 0.0)
        if not (0 <= magnitude < 1):
            raise ValueError(f"相关系数幅度必须在 [0, 1) 范围内，实际为 {magnitude}")

        # 半正定约束
        if K > 1:
            max_magnitude = 1.0 / (K - 1)
            if magnitude > max_magnitude:
                raise ValueError(
                    f"对于 K={K} 个信源，相关系数幅度不能超过 {max_magnitude:.4f}，"
                    f"实际为 {magnitude}；建议的最大幅度已显示在错误信息中"
                )
