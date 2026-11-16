"""将逐次结果整理为正式 MatchedSet，再调用指标插件。"""

from typing import Any

import numpy as np

from arena_api import MatchedSet, MetricValue, kit

from ..runner.results import ExperimentResult, SweepPointResult


def evaluate_metrics(
    result: ExperimentResult, point: SweepPointResult, label: str
) -> dict[str, MetricValue]:
    """所有指标插件共享匹配输入，未运行试验不进入分母。"""
    from ..plugins import resolve_plugin
    from ..storage.contract import trial_status

    trials = [t for t in point.trials if trial_status(t, label) != 7]
    width = max((len(t.truth_angles) for t in trials if t.truth_angles is not None), default=0)
    estimate_width = max(
        (len(t.estimates[label].angles) for t in trials if label in t.estimates), default=0
    )
    truth = np.full((len(trials), width), np.nan)
    matched = truth.copy()
    estimates = np.full((len(trials), estimate_width), np.nan)
    counts = np.zeros(len(trials), dtype=int)
    inferred = np.full(len(trials), -1, dtype=int)
    failed = np.asarray([label not in t.estimates for t in trials], dtype=bool)
    spectra = []
    resolved = []
    for i, trial in enumerate(trials):
        angles = trial.truth_angles if trial.truth_angles is not None else np.array([])
        counts[i] = len(angles)
        truth[i, : len(angles)] = angles
        est = trial.estimates.get(label)
        spectra.append(est.spectrum if est else None)
        resolved.append(est.info.get("resolved_by_spectrum", np.nan) if est else 0)
        if est is not None:
            inferred[i] = len(est.angles)
            estimates[i, : len(est.angles)] = est.angles
            pairs, _ = kit.hungarian_matching(est.angles, angles)
            for ei, si in pairs:
                matched[i, si] = est.angles[ei]
    ms = MatchedSet(
        truth,
        counts,
        estimates,
        inferred,
        matched,
        np.abs(matched - truth),
        failed,
        np.asarray([t.times_ms.get(label, np.nan) for t in trials]),
        spectra,
        {"resolved_by_spectrum": np.asarray(resolved, dtype=float)},
        result.config.get("scenario", {}),
    )
    configuration = result.config.get("metrics", {})
    params: dict[str, Any] = configuration.get("params", {})
    output = {}
    for identifier in configuration.get("include", ["rmse", "success_rate", "resolution", "time"]):
        if identifier == "crb":
            continue
        name = "resolution_prob" if identifier == "resolution" else identifier
        cls = resolve_plugin("metric", name, configuration.get("origins", {}).get(name))
        value = cls().compute(ms, cls.Params(**params.get(name, {})))
        if not isinstance(value, MetricValue):
            raise ValueError(f"指标 {name} 必须返回 MetricValue")
        output[name] = value
    return output
