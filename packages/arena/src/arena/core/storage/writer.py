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
        import hashlib
        from datetime import datetime

        metadata = dict(result.metadata)
        for filename, patch in metadata.pop("_patches", {}).items():
            patch_directory = self.output_dir / "algorithm_patches"
            patch_directory.mkdir(exist_ok=True)
            (patch_directory / Path(filename).name).write_text(patch, encoding="utf-8")
        started = metadata.get("start_time", time.time())
        elapsed = metadata.get("elapsed_seconds", 0)
        metadata.update(
            schema_version=1,
            id=self.output_dir.name,
            name=result.config.get("name", ""),
            created_at=metadata.get(
                "created_at", datetime.fromtimestamp(started).astimezone().isoformat()
            ),
            started_at=datetime.fromtimestamp(started).astimezone().isoformat(),
            finished_at=(
                datetime.fromtimestamp(started + elapsed).astimezone().isoformat()
                if metadata.get("status") in {"completed", "cancelled", "failed"}
                else None
            ),
            elapsed_s=elapsed,
            config_hash="sha256:"
            + hashlib.sha256(
                json.dumps(
                    document, sort_keys=True, separators=(",", ":"), ensure_ascii=False
                ).encode("utf-8")
            ).hexdigest(),
        )
        metadata.setdefault("mode", "script")
        metadata.setdefault("benchmark", None)
        metadata.setdefault("warnings", [])
        metadata.setdefault("history", [])
        self._write_json(self.output_dir / "meta.json", metadata)
        notes_path = self.output_dir / "notes.json"
        if not notes_path.exists():
            self._write_json(
                notes_path,
                {
                    "schema_version": 1,
                    "display_name": None,
                    "notes": "",
                    "tags": result.config.get("tags", []),
                    "starred": False,
                    "updated_at": datetime.now().astimezone().isoformat(),
                },
            )

        # 写入试验结果
        self._write_summary(result)
        self._write_trials(result)

        details = [
            {
                "point": p.point_idx,
                "trial": t.trial_idx,
                "errors": t.errors,
                "info": {label: dict(est.info) for label, est in t.estimates.items()},
                "source_count": t.source_count,
            }
            for p in result.points
            for t in p.trials
        ]
        from .contract import trial_status

        grouped: dict[tuple[str, str], dict[str, Any]] = {}
        for point in result.points:
            for trial in point.trials:
                for label, message in trial.errors.items():
                    stage = "load" if message.startswith("load/configure") else "estimate"
                    group = grouped.setdefault(
                        (label, stage), {"label": label, "stage": stage, "errors": []}
                    )
                    detail = trial.error_details.get(label, {})
                    existing = next(
                        (item for item in group["errors"] if item["message"] == message), None
                    )
                    if existing:
                        existing["count"] += 1
                    else:
                        group["errors"].append(
                            {
                                "status": [
                                    "ok",
                                    "exception",
                                    "bad_output",
                                    "nan_output",
                                    "out_of_range",
                                    "estimation_error",
                                    "skipped",
                                    "not_run",
                                ][trial_status(trial, label)],
                                "type": detail.get("type", "RuntimeError"),
                                "message": message,
                                "first_at": {"point": point.point_idx, "trial": trial.trial_idx},
                                "count": 1,
                                "traceback": detail.get("traceback", ""),
                            }
                        )
        self._write_json(
            self.output_dir / "errors.json",
            {
                "schema_version": 1,
                "trials": details,
                "algorithms": list(grouped.values()),
            },
        )

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
        data["trial_indices"] = np.asarray(
            [[t.trial_idx for t in p.trials] for p in result.points], dtype=np.int64
        )
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
            if result.config.get("options", {}).get("save_estimates", True):
                data[f"{label}__estimates"] = estimates_padded
            data[f"{label}__times_ms"] = np.array(times_list).reshape(num_points, num_trials)
            data[f"{label}__failed"] = np.array(failed_list).reshape(num_points, num_trials)

        for pi, point in enumerate(result.points):
            for ti, trial in enumerate(point.trials):
                if trial.observation is not None:
                    data[f"observation__{pi}__{ti}"] = trial.observation
                for label, estimate in trial.estimates.items():
                    if estimate.spectrum is not None:
                        prefix = f"spectrum__{pi}__{ti}__{label}"
                        data[prefix + "__grid"] = estimate.spectrum.grid
                        data[prefix + "__values"] = estimate.spectrum.values
                        data[prefix + "__kind"] = np.asarray(estimate.spectrum.kind)

        # 写入 npz
        from .contract import standard_arrays

        summary = json.loads((self.output_dir / "summary.json").read_text(encoding="utf-8"))
        standard = standard_arrays(result, algo_labels, summary)
        data.update(standard)
        checkpoint_dir = self.output_dir / "points"
        if result.metadata.get("status") == "running":
            checkpoint_dir.mkdir(exist_ok=True)
            for pi, point in enumerate(result.points):
                if counts[pi] < result.config.get("trials", 1):
                    continue
                sliced = {}
                for key, value in standard.items():
                    shared = key.startswith("impairment__") or (
                        key.startswith("spectrum__") and not key.endswith("__values")
                    )
                    sliced[key] = value if shared else value[pi]
                self._write_npz(checkpoint_dir / f"p_{point.point_idx:03d}.npz", sliced)
        self._write_npz(self.output_dir / "results.npz", data)
        if result.metadata.get("status") in {"completed", "cancelled"} and checkpoint_dir.exists():
            for path in checkpoint_dir.glob("p_[0-9][0-9][0-9]*.npz"):
                path.unlink()
            if not any(checkpoint_dir.iterdir()):
                checkpoint_dir.rmdir()

    def _write_summary(self, result: ExperimentResult) -> None:
        """写入汇总统计。

        Args:
            result: 实验结果
        """
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

        summary["schema_version"] = 1
        summary["complete"] = result.metadata.get("status") == "completed"
        summary["type"] = config.type
        summary["trials"] = config.trials
        summary["algorithms"] = [
            {
                "label": label,
                "id": next((a.id for a in config.algorithms if a.get_label() == label), label),
                "status": "ok"
                if any(label in t.estimates for p in result.points for t in p.trials)
                else "failed",
            }
            for label in algo_labels
        ]

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
                    random_index = (
                        trial.trial_idx
                        if config.options.common_random_numbers
                        else point.point_idx * config.trials + trial.trial_idx
                    )
                    scene, array = build_scene(point_config, random_index)
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
                from ..metrics.summary import point_metrics

                metrics = point_metrics(result, point, label)

                point_summary["algorithms"][label] = metrics

            summary["points"].append(point_summary)

        summary["metrics"] = {}
        for selection in config.metrics.include:
            if selection == "crb":
                continue
            identifier = "resolution_prob" if selection == "resolution" else selection
            summary["metrics"][identifier] = {
                field: [
                    [
                        p["algorithms"][label]["metric_values"][identifier][field]
                        for label in algo_labels
                    ]
                    for p in summary["points"]
                ]
                for field in ("value", "n_used")
            }
        summary["crb"] = (
            {"value": [p.get("crb_deg") for p in summary["points"]]}
            if "crb" in config.metrics.include
            else None
        )
        summary["sweep"] = (
            {**config.sweep.model_dump(mode="json"), "points_done": len(result.points)}
            if config.sweep
            else None
        )
        summary["errors"] = [
            [sum(label in t.errors for t in point.trials) for label in algo_labels]
            for point in result.points
        ]
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
