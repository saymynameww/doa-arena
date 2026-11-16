"""数据格式规范第 4 章的标准结果数组，兼容旧版读取键。"""

from typing import Any

import numpy as np

from arena_api import kit

from ..runner.results import ExperimentResult, TrialResult


def trial_status(trial: TrialResult, label: str) -> int:
    """按规范 4.6 节区分失败、跳过和未运行。"""
    if label in trial.estimates:
        return 0
    error = trial.errors.get(label, "")
    if not error or error.startswith("load/configure"):
        return 7
    if "连续错误达到上限" in error:
        return 6
    for prefix, code in (
        ("bad_output", 2),
        ("nan_output", 3),
        ("out_of_range", 4),
        ("estimation_error", 5),
    ):
        if error.startswith(prefix):
            return code
    return 1


def standard_arrays(
    result: ExperimentResult, labels: list[str], summary: dict[str, Any]
) -> dict[str, np.ndarray]:
    """生成 P×A×T 维度数组，未运行位置保持状态 7 和 NaN。"""
    from ..config import ExperimentConfig
    from ..runner.core import build_scene

    points = len(result.points)
    trials = max((len(point.trials) for point in result.points), default=0)
    algorithms = len(labels)
    truth_width = max(
        (
            len(t.truth_angles)
            for p in result.points
            for t in p.trials
            if t.truth_angles is not None
        ),
        default=0,
    )
    estimate_width = max(
        (len(e.angles) for p in result.points for t in p.trials for e in t.estimates.values()),
        default=1,
    )
    estimate_width = max(1, estimate_width)
    shape = (points, algorithms, trials)
    truth = np.full((points, trials, truth_width), np.nan)
    counts = np.zeros((points, trials), dtype=np.int32)
    given = np.full(shape, -1, dtype=np.int32)
    estimates = np.full((*shape, estimate_width), np.nan)
    matched = np.full((*shape, truth_width), np.nan)
    inferred = np.full(shape, -1, dtype=np.int32)
    status = np.full(shape, 7, dtype=np.uint8)
    elapsed = np.full(shape, np.nan)
    for pi, point in enumerate(result.points):
        for ti, trial in enumerate(point.trials):
            angles = trial.truth_angles if trial.truth_angles is not None else np.array([])
            truth[pi, ti, : len(angles)] = angles
            counts[pi, ti] = len(angles)
            for ai, label in enumerate(labels):
                given[pi, ai, ti] = (
                    trial.source_count if trial.source_count is not None else len(angles)
                )
                status[pi, ai, ti] = trial_status(trial, label)
                elapsed[pi, ai, ti] = trial.times_ms.get(label, np.nan)
                if label in trial.estimates:
                    estimate = trial.estimates[label]
                    inferred[pi, ai, ti] = len(estimate.angles)
                    estimates[pi, ai, ti, : len(estimate.angles)] = estimate.angles
                    pairs, _ = kit.hungarian_matching(estimate.angles, angles)
                    for ei, si in pairs:
                        matched[pi, ai, ti, si] = estimate.angles[ei]
    data = {
        "truth": truth,
        "K": counts,
        "K_given": given,
        "sweep_values": np.asarray(
            [p.sweep_value if p.sweep_value is not None else np.nan for p in result.points]
        ),
    }
    if result.config.get("options", {}).get("save_estimates", True):
        data.update(
            estimates=estimates, matched=matched, K_hat=inferred, status=status, time_ms=elapsed
        )
    for name, metric in summary.get("metrics", {}).items():
        data[f"metric__{name}__value"] = np.asarray(metric["value"], dtype=float)
        data[f"metric__{name}__n_used"] = np.asarray(metric["n_used"], dtype=np.int32)
    if summary.get("crb"):
        data["crb"] = np.asarray(summary["crb"]["value"], dtype=float)
    for ai, label in enumerate(labels):
        spectra = [
            (pi, ti, t.estimates[label].spectrum)
            for pi, p in enumerate(result.points)
            for ti, t in enumerate(p.trials)
            if label in t.estimates and t.estimates[label].spectrum is not None
        ]
        if spectra:
            first = spectra[0][2]
            assert first is not None
            # 扫描网格参数时各点可能不同，旧版逐次键保留完整网格。
            if all(np.array_equal(s.grid, first.grid) for _, _, s in spectra if s is not None):
                values = np.full((points, trials, len(first.grid)), np.nan)
                for pi, ti, spectrum in spectra:
                    assert spectrum is not None
                    values[pi, ti] = spectrum.values
                data[f"spectrum__{ai}__grid"] = first.grid
                data[f"spectrum__{ai}__values"] = values
                data[f"spectrum__{ai}__kind"] = np.asarray(
                    {"power": 0, "pseudo": 1, "probability": 2}[first.kind], dtype=np.uint8
                )
    observations = [t.observation for p in result.points for t in p.trials]
    saved_observations = [x for x in observations if x is not None]
    if saved_observations and len(saved_observations) == len(observations):
        data["observation__X"] = np.stack(saved_observations).reshape(
            points, trials, *saved_observations[0].shape
        )
    if points:
        scene, array = build_scene(ExperimentConfig.model_validate(result.config))
        for index, instance in enumerate(i for i in scene.impairments if i.draw is not None):
            assert instance.draw is not None
            for name, value in instance.draw.items():
                data[f"impairment__{index}__draw__{name}"] = np.asarray(value)
            for name, value in instance.impairment.describe(
                instance.draw, instance.params, array.M
            ).items():
                data[f"impairment__{index}__value__{name}"] = np.asarray(value)
    return data
