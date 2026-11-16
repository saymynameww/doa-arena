"""信号生成器。

生成复高斯随机信号（V1默认）。
"""

from __future__ import annotations

import numpy as np


class SignalGenerator:
    """信号生成器。

    生成零均值复高斯随机信号。
    """

    def __init__(
        self,
        K: int,
        snr_db: float | list[float],
        noise_power: float = 1.0,
    ) -> None:
        """初始化。

        Args:
            K: 信源数
            snr_db: SNR（dB），标量或长度为 K 的列表
            noise_power: 噪声功率（线性值）
        """
        self.K = K
        self.noise_power = noise_power

        # SNR 转功率
        if isinstance(snr_db, (int, float)):
            snr_db = [snr_db] * K

        if len(snr_db) != K:
            raise ValueError(f"SNR 长度必须为 {K}，实际为 {len(snr_db)}")

        # σ_k² = σ_n² · 10^(SNR/10)
        self.signal_powers = np.array([noise_power * (10 ** (snr / 10)) for snr in snr_db])

    def generate(
        self,
        N: int,
        rng: np.random.Generator,
    ) -> np.ndarray:
        """生成独立信源（不相干）。

        Args:
            N: 快拍数
            rng: 随机数生成器

        Returns:
            信源矩阵，形状 (K, N)，complex128
        """
        # 独立复高斯：实部和虚部独立的高斯
        # E[|s_k|²] = σ_k²
        # 实部和虚部各占一半功率
        real = rng.normal(0, 1, (self.K, N))
        imag = rng.normal(0, 1, (self.K, N))

        S = (real + 1j * imag) / np.sqrt(2)

        # 缩放到目标功率
        for k in range(self.K):
            S[k, :] *= np.sqrt(self.signal_powers[k])

        return S

    def generate_noise(
        self,
        M: int,
        N: int,
        rng: np.random.Generator,
    ) -> np.ndarray:
        """生成白噪声。

        Args:
            M: 阵元数
            N: 快拍数
            rng: 随机数生成器

        Returns:
            噪声矩阵，形状 (M, N)，complex128
        """
        real = rng.normal(0, 1, (M, N))
        imag = rng.normal(0, 1, (M, N))

        W = (real + 1j * imag) / np.sqrt(2)
        W *= np.sqrt(self.noise_power)

        return W
