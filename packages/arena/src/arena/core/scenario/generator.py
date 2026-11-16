"""场景生成器。

按需求 2.2-2.4 节生成接收数据，支持误差。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from arena_api import ArrayDescriptor, Impairment, Observation

from ..rng import TrialRNG
from ..signals import CorrelationMatrix, generate_correlated_sources


@dataclass
class ImpairmentInstance:
    """误差实例。"""

    impairment: Impairment
    params: Any
    realization_mode: str  # "fixed" or "per_trial"
    draw: dict[str, np.ndarray] | None = None  # 固定误差的抽取结果


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

    生成接收数据，支持误差。
    """

    def __init__(
        self,
        config: ScenarioConfig,
        impairments: list[ImpairmentInstance] | None = None,
    ) -> None:
        """初始化。

        Args:
            config: 场景配置
            impairments: 误差列表
        """
        self.config = config
        self.impairments = impairments or []

        # 验证
        if len(config.angles) != config.K:
            raise ValueError(f"角度数量 {len(config.angles)} 与信源数 {config.K} 不匹配")

        # 预计算导向矢量（标称）
        self.A_nominal = config.array.steering(config.angles)  # (M, K)

        # 按阶段分组误差
        self.impairments_by_stage = self._group_impairments_by_stage()

    def _group_impairments_by_stage(
        self,
    ) -> dict[str, list[ImpairmentInstance]]:
        """按阶段分组误差。"""
        stages = {
            "positions": [],
            "manifold": [],
            "signal": [],
            "output": [],
        }

        for imp_inst in self.impairments:
            # 获取阶段
            if hasattr(imp_inst.impairment, "stage_for"):
                stage = imp_inst.impairment.stage_for(imp_inst.params)
            else:
                stage = imp_inst.impairment.stage

            stages[stage].append(imp_inst)

        return stages

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

        # 阶段 1: 位置误差
        positions = self.config.array.positions.copy()
        for imp_inst in self.impairments_by_stage["positions"]:
            draw = self._get_draw(imp_inst, trial_rng, M)
            positions = imp_inst.impairment.apply(
                positions,
                draw,
                imp_inst.params,
            )

        # 用实际位置重新计算导向矢量
        if self.impairments_by_stage["positions"]:
            # 简化：使用实际位置计算（完整版需要阵列插件）
            # 这里假设 ULA
            from ..arrays import ULA

            ula = ULA()
            A = ula._compute_steering(positions, self.config.angles)
        else:
            A = self.A_nominal.copy()

        # 阶段 2: 流形误差（幅相、互耦）
        for imp_inst in self.impairments_by_stage["manifold"]:
            draw = self._get_draw(imp_inst, trial_rng, M)
            A = imp_inst.impairment.apply(A, draw, imp_inst.params)

        # 生成信源
        rng_sources = trial_rng.for_sources(K)
        S = generate_correlated_sources(
            self.config.correlation,
            N,
            rng_sources,
        )  # (K, N)

        # 无噪数据：AS = A·S
        AS = A @ S

        # 阶段 3: 信号误差（阵元故障 noise_only 模式）
        for imp_inst in self.impairments_by_stage["signal"]:
            draw = self._get_draw(imp_inst, trial_rng, M)
            AS = imp_inst.impairment.apply(AS, draw, imp_inst.params)

        # 生成噪声
        rng_noise = trial_rng.for_noise()
        real = rng_noise.normal(0, 1, (M, N))
        imag = rng_noise.normal(0, 1, (M, N))
        W = (real + 1j * imag) / np.sqrt(2) * np.sqrt(self.config.noise_power)

        # 含噪数据：X = AS + W
        X = AS + W

        # 阶段 4: 输出误差（阵元故障 zero 模式）
        for imp_inst in self.impairments_by_stage["output"]:
            draw = self._get_draw(imp_inst, trial_rng, M)
            X = imp_inst.impairment.apply(X, draw, imp_inst.params)

        return Observation(X=X, K=K)

    def _get_draw(
        self,
        imp_inst: ImpairmentInstance,
        trial_rng: TrialRNG,
        M: int,
    ) -> dict[str, np.ndarray]:
        """获取误差实现。

        Args:
            imp_inst: 误差实例
            trial_rng: 试验随机数
            M: 阵元数

        Returns:
            误差实现
        """
        if imp_inst.realization_mode == "fixed":
            # 固定误差：使用预先抽取的
            if imp_inst.draw is None:
                # 第一次，需要抽取
                rng = trial_rng.for_impairment(
                    imp_inst.impairment.id,
                    "fixed",
                )
                imp_inst.draw = imp_inst.impairment.sample(rng, M)
            return imp_inst.draw
        else:
            # 每次随机
            rng = trial_rng.for_impairment(
                imp_inst.impairment.id,
                "random",
            )
            return imp_inst.impairment.sample(rng, M)


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
