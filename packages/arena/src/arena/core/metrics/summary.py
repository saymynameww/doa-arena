"""逐次结果的统一指标汇总，供存储和导出使用。"""

from typing import Any

import numpy as np

from arena_api import Estimate

from ..runner.results import ExperimentResult, SweepPointResult
from .compute import compute_metrics


def algorithm_labels(result: ExperimentResult) -> list[str]:
    """保留所有成功或失败的算法，避免首个试验失败后漏列。"""
    if result.saved_summary is not None:
        return [
            item["label"] if isinstance(item, dict) else item
            for item in result.saved_summary["algorithms"]
        ]
    return list(
        dict.fromkeys(
            label
            for point in result.points
            for trial in point.trials
            for label in [*trial.estimates, *trial.errors]
        )
    )


def point_metrics(result: ExperimentResult, point: SweepPointResult, label: str) -> dict[str, Any]:
    """使用逐次真值和配置门限汇总一个算法的一个扫描点。"""
    if not result.config.get("options", {}).get("save_estimates", True):
        if result.saved_summary is not None:
            return dict(result.saved_summary["points"][point.point_idx]["algorithms"][label])
    angles = result.config.get("scenario", {}).get("sources", {}).get("angles", {})
    from ..storage.contract import trial_status

    trials = [trial for trial in point.trials if trial_status(trial, label) != 7]
    fallback = np.asarray(angles.get("values") or [], dtype=float)
    truths = [
        trial.truth_angles if trial.truth_angles is not None else fallback for trial in trials
    ]
    threshold = (
        result.config.get("metrics", {})
        .get("params", {})
        .get("success_rate", {})
        .get("threshold_deg", 1.0)
    )
    estimates = [trial.estimates.get(label, Estimate.from_angles([])) for trial in trials]
    rmse_options = result.config.get("metrics", {}).get("params", {}).get("rmse", {})
    metrics: dict[str, Any] = dict(
        compute_metrics(estimates, fallback, threshold_deg=threshold, truths=truths, **rmse_options)
    )
    durations = [trial.times_ms[label] for trial in trials if label in trial.times_ms]
    metrics["avg_time_ms"] = float(np.mean(durations)) if durations else np.nan
    from dataclasses import asdict

    from .plugins import evaluate_metrics

    values = evaluate_metrics(result, point, label)
    metrics["metric_values"] = {name: asdict(value) for name, value in values.items()}
    for value in metrics["metric_values"].values():
        if value["per_source"] is not None:
            value["per_source"] = value["per_source"].tolist()
    for name, key in (
        ("rmse", "rmse_mean"),
        ("success_rate", "success_rate"),
        ("resolution_prob", "resolution_probability"),
    ):
        if name in values:
            metrics[key] = values[name].value
    if "rmse" in values:
        metrics["num_valid"] = values["rmse"].n_used
    return metrics
