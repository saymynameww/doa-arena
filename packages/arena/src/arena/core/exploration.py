"""架构 5.12 节的细粒度脚本入口，复用正式场景和算法实现。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from arena_api import Algorithm, ArrayDescriptor, Observation

from .config import ExperimentConfig, ScenarioConfig
from .crb import compute_stochastic_crb
from .plugins import resolve_algorithm
from .rng import RNGTree
from .runner.core import build_scene


@dataclass(frozen=True)
class Truth:
    """仅供评测使用的真值，算法 estimate 不接收此对象。"""

    angles: np.ndarray


@dataclass(frozen=True)
class SampledTrial:
    """交互式调试样本，观测与真值分开。"""

    observation: Observation
    array: ArrayDescriptor
    truth: Truth
    seed: int
    trial_index: int

    def algorithm_rng(self, label: str) -> np.random.Generator:
        """沿正式 Runner 的派生路径生成算法随机数。"""
        return (
            RNGTree(self.seed)
            .for_trial(self.trial_index)
            .for_impairment("algorithm:" + label, "random")
        )


class Scenario:
    """无需工作目录的场景配置与单次采样接口。"""

    def __init__(self, config: dict[str, Any] | ScenarioConfig) -> None:
        self.config = ScenarioConfig.model_validate(config)

    @classmethod
    def from_dict(cls, config: dict[str, Any]) -> Scenario:
        """从场景字典构造，与实验配置 scenario 结构一致。"""
        return cls(config)

    def sample(self, trial_index: int = 0, *, seed: int | None = None) -> SampledTrial:
        """按试验序号采样；显式 seed 覆盖场景种子，保持派生路径一致。"""
        config = self.config.model_copy(deep=True)
        if seed is not None:
            config.seed = seed
        experiment = ExperimentConfig.model_validate({"scenario": config})
        scene, _ = build_scene(experiment, trial_index)
        angles = scene.config.angles.copy()
        angles.flags.writeable = False
        return SampledTrial(
            scene.generate(RNGTree(config.seed).for_trial(trial_index)),
            scene.algorithm_array(RNGTree(config.seed).for_trial(trial_index)),
            Truth(angles),
            config.seed,
            trial_index,
        )


def algorithm(identifier: str, **params: Any) -> Algorithm:
    """构造单次调试算法，正式实验请使用 algorithm_spec。"""
    cls = resolve_algorithm(identifier)
    instance = cls()
    instance._once_params = cls.Params.model_validate(params).model_dump(mode="json")
    return instance


def crb(scenario: Scenario) -> np.ndarray:
    """返回标称阵列随机信号 CRB 方差，单位为平方度。"""
    scene, array = build_scene(ExperimentConfig.model_validate({"scenario": scenario.config}))
    return compute_stochastic_crb(
        array,
        scene.config.angles,
        np.asarray(scene.config.snr_db),
        scene.config.N,
        signal_covariance=scene.config.correlation.to_matrix(),
        noise_power=scene.config.noise_power,
    )


def preview_scenario(config: ScenarioConfig) -> dict[str, Any]:
    """为所有前端提供阵列规模、信源方向和物理间距显示数据。"""
    scene, array = build_scene(ExperimentConfig.model_validate({"scenario": config}))
    spacing = array.ula_spacing
    rng = RNGTree(config.seed).for_trial(0)
    positions = array.positions.copy()
    for item in scene.impairments_by_stage["positions"]:
        positions = item.impairment.apply(
            positions, scene._get_draw(item, rng, array.M), item.params
        )
    mask = scene.algorithm_array(rng).element_mask
    angle_range = config.sources.angles.range_deg
    return {
        "elements": array.M,
        "angles": scene.config.angles.tolist() if config.sources.angles.mode != "random" else [],
        "ranges": [{"min": angle_range[0], "max": angle_range[1]}]
        if config.sources.angles.mode == "random" and angle_range is not None
        else [],
        "faulty_elements": np.flatnonzero(~mask).tolist(),
        "positions": positions.tolist(),
        "physical_spacing_cm": spacing * 299792458 / config.array.carrier_hz * 100
        if spacing is not None and config.array.carrier_hz is not None
        else None,
    }
