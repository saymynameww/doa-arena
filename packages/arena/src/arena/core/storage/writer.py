"""结果写入器。

按架构文档第 5.8 节，使用原子写入（临时文件+重命名）。
"""

from __future__ import annotations

import json
import tempfile
import time
from pathlib import Path
from typing import Any

import numpy as np

from ..metrics import compute_metrics
from ..runner.results import ExperimentResult


class ResultWriter:
    """结果写入器。

    负责将实验结果写入磁盘。
    """

    def __init__(self, output_dir: Path) -> None:
        """初始化。

        Args:
            output_dir: 输出目录
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def write_experiment(self, result: ExperimentResult) -> None:
        """写入实验结果。

        Args:
            result: 实验结果
        """
        # 写入配置
        from ..config import ExperimentConfig

        document = ExperimentConfig.model_validate(result.config).to_document()
        self._write_json(self.output_dir / "config.json", document)

        # 写入元信息
        self._write_json(self.output_dir / "meta.json", result.metadata)

        # 写入试验结果
        self._write_trials(result)

        # 计算并写入汇总统计
        self._write_summary(result)

    def _write_trials(self, result: ExperimentResult) -> None:
        """写入逐次试验结果。

        Args:
            result: 实验结果
        """
        from dataclasses import replace

        from ..runner.results import TrialResult

        counts = [len(p.trials) for p in result.points]
        width = max(counts, default=0)
        result = replace(
            result,
            points=[
                replace(
                    p,
                    trials=p.trials
                    + [
                        TrialResult(i, {}, {}, {}, np.array([]))
                        for i in range(len(p.trials), width)
                    ],
                )
                for p in result.points
            ],
        )
        algo_labels = list(
            dict.fromkeys(
                label
                for point in result.points
                for trial in point.trials
                for label in [*trial.estimates, *trial.errors]
            )
        )
        # 准备数据结构
        num_points = len(result.points)
        num_trials = len(result.points[0].trials) if result.points else 0

        data: dict[str, np.ndarray] = {"trial_counts": np.asarray(counts)}
        truths = [trial.truth_angles for point in result.points for trial in point.trials]
        max_truth = max((len(x) for x in truths if x is not None), default=0)
        truth_data = np.full((num_points, num_trials, max_truth), np.nan)
        for i, truth in enumerate(truths):
            if truth is not None:
                truth_data[i // num_trials, i % num_trials, : len(truth)] = truth
        data["truth_angles"] = truth_data

        for label in algo_labels:
            # 收集该算法的所有估计
            estimates_list = []
            times_list = []
            failed_list = []

            for point in result.points:
                for trial in point.trials:
                    if label in trial.estimates:
                        est = trial.estimates[label]
                        estimates_list.append(est.angles)
                        times_list.append(trial.times_ms.get(label, np.nan))
                        failed_list.append(False)
                    else:
                        estimates_list.append(np.array([]))
                        times_list.append(np.nan)
                        failed_list.append(True)

            # 找到最大长度
            max_K = max((len(est) for est in estimates_list), default=0)

            # 填充到统一长度
            estimates_padded = np.full((num_points, num_trials, max_K), np.nan)
            for i, angles in enumerate(estimates_list):
                point_idx = i // num_trials
                trial_idx = i % num_trials
                if len(angles) > 0:
                    estimates_padded[point_idx, trial_idx, : len(angles)] = angles

            # 存储
            data[f"{label}__estimates"] = estimates_padded
            data[f"{label}__times_ms"] = np.array(times_list).reshape(num_points, num_trials)
            data[f"{label}__failed"] = np.array(failed_list).reshape(num_points, num_trials)

        for pi, point in enumerate(result.points):
            for ti, trial in enumerate(point.trials):
                for label, estimate in trial.estimates.items():
                    if estimate.spectrum is not None:
                        prefix = f"spectrum__{pi}__{ti}__{label}"
                        data[prefix + "__grid"] = estimate.spectrum.grid
                        data[prefix + "__values"] = estimate.spectrum.values
                        data[prefix + "__kind"] = np.asarray(estimate.spectrum.kind)

        # 写入 npz
        self._write_npz(self.output_dir / "results.npz", data)

    def _write_summary(self, result: ExperimentResult) -> None:
        """写入汇总统计。

        Args:
            result: 实验结果
        """
        truth_angles = _truth_angles_from_config(result.config)
        from ..config import ExperimentConfig
        from ..crb import compute_stochastic_crb
        from ..runner.core import build_scene, expand_point

        config = ExperimentConfig.model_validate(result.config)

        summary: dict[str, Any] = {
            "algorithms": [],
            "points": [],
        }

        algo_labels = list(
            dict.fromkeys(
                label
                for point in result.points
                for trial in point.trials
                for label in [*trial.estimates, *trial.errors]
            )
        )

        summary["algorithms"] = algo_labels

        # 每个扫描点
        for point in result.points:
            point_summary: dict[str, Any] = {
                "point_idx": point.point_idx,
                "sweep_value": point.sweep_value,
                "algorithms": {},
            }

            if "crb" in config.metrics.include:
                point_config = expand_point(config, point.sweep_value)
                bounds = []
                dynamic = (
                    point_config.scenario.sources.angles.mode == "random"
                    or point_config.scenario.sources.correlation.mode == "coherent"
                )
                for trial in point.trials if dynamic else point.trials[:1]:
                    scene, array = build_scene(point_config, trial.trial_idx)
                    bounds.extend(
                        compute_stochastic_crb(
                            array,
                            scene.config.angles,
                            np.asarray(point_config.scenario.sources.snr_db),
                            scene.config.N,
                            signal_covariance=scene.config.correlation.to_matrix(),
                            noise_power=scene.config.noise_power,
                        ).tolist()
                    )
                point_summary["crb_deg"] = (
                    float(np.sqrt(np.mean(bounds)))
                    if bounds and np.all(np.isfinite(bounds))
                    else None
                )
                if any(x.enabled for x in point_config.scenario.impairments):
                    point_summary["crb_reason"] = "理想标称阵列参考下界，不含阵列误差"
            # 每个算法
            for label in algo_labels:
                # 收集该算法该点的所有估计
                from arena_api import Estimate

                estimates = [
                    trial.estimates.get(label, Estimate.from_angles([])) for trial in point.trials
                ]

                # 计算指标
                threshold = (
                    result.config.get("metrics", {})
                    .get("params", {})
                    .get("success_rate", {})
                    .get("threshold_deg", 1.0)
                )
                truths = [
                    trial.truth_angles if trial.truth_angles is not None else truth_angles
                    for trial in point.trials
                ]
                metrics: dict[str, Any] = dict(
                    compute_metrics(estimates, truth_angles, threshold_deg=threshold, truths=truths)
                )
                times = [
                    trial.times_ms.get(label, np.nan)
                    for trial in point.trials
                    if label in trial.times_ms
                ]
                metrics["avg_time_ms"] = float(np.nanmean(times)) if times else np.nan

                point_summary["algorithms"][label] = metrics

            summary["points"].append(point_summary)

        # 写入
        self._write_json(self.output_dir / "summary.json", summary)

    def _write_json(self, path: Path, data: Any) -> None:
        """原子写入 JSON。"""
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            delete=False,
            suffix=".tmp",
        ) as f:
            json.dump(_json_safe(data), f, indent=2, ensure_ascii=False, allow_nan=False)
            temp_path = f.name
        _replace_with_retry(Path(temp_path), path)

    def _write_npz(self, path: Path, data: dict[str, Any]) -> None:
        """原子写入 npz。"""
        with tempfile.NamedTemporaryFile(
            dir=path.parent,
            delete=False,
            suffix=".tmp",
        ) as f:
            np.savez(f, **data)
            temp_path = f.name
        _replace_with_retry(Path(temp_path), path)


def _truth_angles_from_config(config: dict[str, Any]) -> np.ndarray:
    """从实验配置中提取真实角度，供结果汇总和导出共用。"""
    sources = config.get("scenario", {}).get("sources", {})
    angles = sources.get("angles", {})
    values = angles.get("values") if isinstance(angles, dict) else None
    if values:
        return np.asarray(values, dtype=float)
    count = sources.get("K", 2)
    count = int(count) if isinstance(count, int | float) else int(count["values"][0])
    return np.linspace(-10.0, 10.0, count, dtype=float)


def _json_safe(value: Any) -> Any:
    """JSON 只使用标准有限数值，缺失统计写 null。"""
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_json_safe(v) for v in value]
    if isinstance(value, np.ndarray):
        return _json_safe(value.tolist())
    if isinstance(value, np.generic):
        return _json_safe(value.item())
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def _replace_with_retry(source: Path, target: Path) -> None:
    """允许 Windows 读端关闭短暂占用，始终以重命名保持原子性。"""
    try:
        for attempt in range(8):
            try:
                source.replace(target)
                return
            except PermissionError:
                if attempt == 7:
                    raise
                time.sleep(min(0.01 * 2**attempt, 0.2))
    finally:
        source.unlink(missing_ok=True)
