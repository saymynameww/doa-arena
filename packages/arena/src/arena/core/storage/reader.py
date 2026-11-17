"""从普通文件恢复结果，不依赖服务内存或索引。"""

from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path
from typing import Any, Literal, cast

import numpy as np

from arena_api import Estimate, Spectrum

from ..config import ExperimentConfig
from ..runner.results import ExperimentResult, SweepPointResult, TrialResult


def read_result(directory: Path) -> ExperimentResult:
    """读取配置、逐次真值、估计、耗时和真实空间谱。"""
    directory = Path(directory)
    config = json.loads((directory / "config.json").read_text(encoding="utf-8"))
    config = ExperimentConfig.model_validate(config).model_dump(mode="json")
    metadata = json.loads((directory / "meta.json").read_text(encoding="utf-8"))
    summary = json.loads((directory / "summary.json").read_text(encoding="utf-8"))
    detail_path = directory / "errors.json"
    details = json.loads(detail_path.read_text(encoding="utf-8")) if detail_path.exists() else {}
    details = {(row["point"], row["trial"]): row for row in details.get("trials", [])}
    points = []
    # 先释放磁盘句柄，避免 Windows 检查点替换被图表读取阻塞。
    # 各数组只解码一次，避免逐试验访问 NpzFile 导致重复解压。
    with np.load(BytesIO((directory / "results.npz").read_bytes()), allow_pickle=False) as archive:
        raw = {key: archive[key] for key in archive.files}
        if "truth_angles" not in raw:
            return _read_standard(config, metadata, summary, details, raw)
        labels = [key[:-11] for key in raw if key.endswith("__estimates")]
        shape = raw[labels[0] + "__estimates"].shape if labels else raw["truth_angles"].shape
        for pi in range(shape[0]):
            trials = []
            for ti in range(int(raw["trial_counts"][pi]) if "trial_counts" in raw else shape[1]):
                trial_index = int(raw["trial_indices"][pi, ti]) if "trial_indices" in raw else ti
                detail = details.get((pi, trial_index), {})
                estimates, errors, times = {}, dict(detail.get("errors", {})), {}
                for label in labels:
                    if raw[label + "__failed"][pi, ti]:
                        errors.setdefault(label, "运行错误，详情见 errors.json")
                        continue
                    angles = raw[label + "__estimates"][pi, ti]
                    prefix = f"spectrum__{pi}__{ti}__{label}"
                    spectrum = None
                    if prefix + "__grid" in raw:
                        spectrum = Spectrum(
                            raw[prefix + "__grid"],
                            raw[prefix + "__values"],
                            cast(
                                Literal["power", "pseudo", "probability"],
                                str(raw[prefix + "__kind"].item()),
                            ),
                        )
                    estimates[label] = Estimate(
                        angles[np.isfinite(angles)], spectrum, detail.get("info", {}).get(label, {})
                    )
                    times[label] = float(raw[label + "__times_ms"][pi, ti])
                truth = (
                    raw["truth_angles"][pi, ti]
                    if "truth_angles" in raw
                    else np.asarray(config["scenario"]["sources"]["angles"]["values"])
                )
                trials.append(
                    TrialResult(
                        trial_index,
                        estimates,
                        errors,
                        times,
                        truth[np.isfinite(truth)],
                        raw[f"observation__{pi}__{ti}"]
                        if f"observation__{pi}__{ti}" in raw
                        else None,
                        detail.get("source_count"),
                    )
                )
            point = summary["points"][pi]
            points.append(SweepPointResult(pi, point.get("sweep_value"), trials))
    return ExperimentResult(config, points, metadata, summary)


def _read_standard(
    config: dict[str, Any],
    metadata: dict[str, Any],
    summary: dict[str, Any],
    details: dict,
    raw: Any,
) -> ExperimentResult:
    """只含规范数组的外部文件和 points 恢复结果同样可以读取。"""
    labels = [entry["label"] for entry in summary["algorithms"]]
    points = []
    for pi in range(raw["truth"].shape[0]):
        trials = []
        for ti in range(raw["truth"].shape[1]):
            count = int(raw["K"][pi, ti])
            if count < 1:
                continue
            estimates, errors, times = {}, {}, {}
            for ai, label in enumerate(labels):
                status = int(raw["status"][pi, ai, ti]) if "status" in raw else 7
                if status == 7:
                    continue
                if status:
                    messages = {
                        2: "bad_output",
                        3: "nan_output",
                        4: "out_of_range",
                        5: "estimation_error",
                        6: "连续错误达到上限",
                    }
                    errors[label] = (
                        details.get((pi, ti), {})
                        .get("errors", {})
                        .get(label, messages.get(status, "运行错误，详情见 errors.json"))
                    )
                    continue
                angles = raw["estimates"][pi, ai, ti]
                spectrum = None
                prefix = f"spectrum__{ai}"
                if prefix + "__values" in raw:
                    kind = ["power", "pseudo", "probability"][int(raw[prefix + "__kind"])]
                    spectrum = Spectrum(
                        raw[prefix + "__grid"],
                        raw[prefix + "__values"][pi, ti],
                        cast(Literal["power", "pseudo", "probability"], kind),
                    )
                info = details.get((pi, ti), {}).get("info", {}).get(label, {})
                estimates[label] = Estimate(angles[np.isfinite(angles)], spectrum, info)
                times[label] = float(raw["time_ms"][pi, ai, ti])
            trials.append(TrialResult(ti, estimates, errors, times, raw["truth"][pi, ti, :count]))
        value = float(raw["sweep_values"][pi]) if config.get("sweep") else None
        points.append(SweepPointResult(pi, value, trials))
    return ExperimentResult(config, points, metadata, summary)
