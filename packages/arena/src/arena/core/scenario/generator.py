"""场景生成器。

按需求 2.2-2.4 节生成接收数据。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from arena_api import ArrayDescriptor, Observation

from ..rng import TrialRNG
from ..signals import CorrelationMatrix, generate_correlated_sources


@dataclass
class ScenarioConfig:
    """场景配置（简化版，用于M1测试）。

    完整配置结构将在后续实现。
    """

    # 阵列
    array: ArrayDescriptor

    # 信源
    K: int
    angles: np.ndarray  # 形状 (K,)，度
    snr_db: float | list[float]

    # 快拍数
    N: int

    # 相关性
    correlation: CorrelationMatrix

    # 噪声功率
    noise_power: float = 1.0


class ScenarioGenerator:
    """场景生成器。

    生成标称模型（无误差）下的接收数据。
    """

    def __init__(self, config: ScenarioConfig) -> None:
        """初始化。

        Args:
            config: 场景配置
        """
        self.config = config

        # 验证
        if len(config.angles) != config.K:
            raise ValueError(
                f"角度数量 {len(config.angles)} 与信源数 {config.K} 不匹配"
            )

        # 预计算导向矢量
        self.A = config.array.steering(config.angles)  # (M, K)

    def generate(self, trial_rng: TrialRNG) -> Observation:
        """生成一次试验数据。

        Args:
            trial_rng: 试验随机数管理器

        Returns:
            观测数据
        """
        M = self.config.array.M
        N = self.config.N
        K = self.config.K

        # 生成信源
        rng_sources = trial_rng.for_sources(K)
        S = generate_correlated_sources(
            self.config.correlation,
            N,
            rng_sources,
        )  # (K, N)

        # 生成噪声
        rng_noise = trial_rng.for_noise()
        real = rng_noise.normal(0, 1, (M, N))
        imag = rng_noise.normal(0, 1, (M, N))
        W = (real + 1j * imag) / np.sqrt(2) * np.sqrt(self.config.noise_power)

        # 接收数据：X = A·S + W
        X = self.A @ S + W

        return Observation(X=X, K=K)


def generate_trial_data(
    array: ArrayDescriptor,
    angles: np.ndarray,
    K: int,
    N: int,
    snr_db: float,
    correlation_mode: str = "independent",
    trial_rng: TrialRNG | None = None,
    seed: int | None = None,
) -> Observation:
    """便捷函数：生成单次试验数据。

    Args:
        array: 阵列描述
        angles: 信源角度（度），形状 (K,)
        K: 信源数
        N: 快拍数
        snr_db: SNR（dB）
        correlation_mode: 相关性模式
        trial_rng: 试验随机数管理器（优先使用）
        seed: 随机种子（trial_rng 为 None 时使用）

    Returns:
        观测数据
    """
    # 随机数
    if trial_rng is None:
        if seed is None:
            seed = 42
        from ..rng import RNGTree

        tree = RNGTree(seed)
        trial_rng = tree.for_trial(0)

    # 信源功率
    noise_power = 1.0
    signal_power = noise_power * (10 ** (snr_db / 10))
    powers = np.full(K, signal_power)

    # 相关性
    if correlation_mode == "independent":
        corr = CorrelationMatrix.independent(powers)
    elif correlation_mode == "coherent":
        alpha = np.ones(K, dtype=complex)
        alpha[0] = 1.0
        for k in range(1, K):
            # 随机相位
            phase = trial_rng.for_sources(K).uniform(0, 2 * np.pi)
            alpha[k] = np.sqrt(powers[k] / powers[0]) * np.exp(1j * phase)
        corr = CorrelationMatrix.coherent(powers, alpha)
    else:
        raise ValueError(f"未知的相关性模式：{correlation_mode}")

    # 场景配置
    config = ScenarioConfig(
        array=array,
        K=K,
        angles=angles,
        snr_db=snr_db,
        N=N,
        correlation=corr,
        noise_power=noise_power,
    )

    # 生成
    gen = ScenarioGenerator(config)
    return gen.generate(trial_rng)
