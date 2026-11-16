"""逐次结果的统一指标汇总，供存储和导出使用。"""

from typing import Any

import numpy as np

from arena_api import Estimate

from ..runner.results import ExperimentResult, SweepPointResult
from .compute import compute_metrics


def algorithm_labels(result: ExperimentResult) -> list[str]:
    """保留所有成功或失败的算法，避免首个试验失败后漏列。"""
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
    angles = result.config.get("scenario", {}).get("sources", {}).get("angles", {})
    fallback = np.asarray(angles.get("values") or [], dtype=float)
    truths = [
        trial.truth_angles if trial.truth_angles is not None else fallback for trial in point.trials
    ]
    threshold = (
        result.config.get("metrics", {})
        .get("params", {})
        .get("success_rate", {})
        .get("threshold_deg", 1.0)
    )
    estimates = [trial.estimates.get(label, Estimate.from_angles([])) for trial in point.trials]
    metrics: dict[str, Any] = dict(
        compute_metrics(estimates, fallback, threshold_deg=threshold, truths=truths)
    )
    durations = [trial.times_ms[label] for trial in point.trials if label in trial.times_ms]
    metrics["avg_time_ms"] = float(np.mean(durations)) if durations else np.nan
    return metrics
