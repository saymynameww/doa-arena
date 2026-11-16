"""逐源指标和 CRB，供结果文件、重算和脚本共用。"""

from typing import Any

import numpy as np

from arena_api import Estimate, kit

from ..config import ExperimentConfig
from ..crb import compute_stochastic_crb
from ..runner.results import ExperimentResult


def rmse(estimates: list[Estimate], trials: list[Any]) -> float:
    """从调试样本计算 RMSE，默认只纳入估计数正确的试验。"""
    from .compute import compute_metrics

    if len(estimates) != len(trials):
        raise ValueError("估计数量与试验数量不同，请传入一一对应的列表")
    return compute_metrics(estimates, np.array([]), truths=[t.truth.angles for t in trials])[
        "rmse_mean"
    ]


def sourcewise_arrays(result: ExperimentResult, labels: list[str]) -> dict[str, np.ndarray]:
    """生成规范逐源 RMSE 与 CRB，随机 K 时不输出 crb_per_source。"""
    from ..runner.core import build_scene, expand_point

    config = ExperimentConfig.model_validate(result.config)
    width = max(
        (
            len(t.truth_angles)
            for p in result.points
            for t in p.trials
            if t.truth_angles is not None
        ),
        default=0,
    )
    values = np.full((len(result.points), len(labels), width), np.nan)
    bounds = np.full((len(result.points), width), np.nan)
    for pi, point in enumerate(result.points):
        point_config = expand_point(config, point.sweep_value)
        for ai, label in enumerate(labels):
            squared: list[list[float]] = [[] for _ in range(width)]
            for trial in point.trials:
                if label not in trial.estimates or trial.truth_angles is None:
                    continue
                estimate = trial.estimates[label]
                truth = trial.truth_angles
                if (
                    len(estimate.angles) != len(truth)
                    and not config.metrics.params.rmse.include_failed
                ):
                    continue
                pairs, _ = kit.hungarian_matching(estimate.angles, truth)
                errors = np.full(len(truth), config.metrics.params.rmse.penalty_deg**2)
                for ei, si in pairs:
                    errors[si] = (estimate.angles[ei] - truth[si]) ** 2
                for si, error in enumerate(errors):
                    squared[si].append(float(error))
            for si, samples in enumerate(squared):
                if samples:
                    values[pi, ai, si] = np.sqrt(np.mean(samples))
        if "crb" in config.metrics.include and isinstance(point_config.scenario.sources.K, int):
            trial_bounds = []
            dynamic = point_config.scenario.sources.angles.mode == "random" or (
                point_config.scenario.sources.correlation.mode == "coherent"
                and point_config.scenario.sources.correlation.phases_deg == "random"
            )
            for trial in point.trials if dynamic else point.trials[:1]:
                index = (
                    trial.trial_idx
                    if config.options.common_random_numbers
                    else (point.point_idx * config.trials + trial.trial_idx)
                )
                scene, array = build_scene(point_config, index)
                trial_bounds.append(
                    compute_stochastic_crb(
                        array,
                        scene.config.angles,
                        np.asarray(scene.config.snr_db),
                        scene.config.N,
                        signal_covariance=scene.config.correlation.to_matrix(),
                        noise_power=scene.config.noise_power,
                    )
                )
            if trial_bounds:
                mean = np.sqrt(np.mean(trial_bounds, axis=0))
                bounds[pi, : len(mean)] = mean
    arrays: dict[str, np.ndarray] = {}
    if "rmse" in config.metrics.include:
        arrays["metric__rmse__per_source"] = values
    if "crb" in config.metrics.include and isinstance(config.scenario.sources.K, int):
        arrays["crb_per_source"] = bounds
    return arrays
