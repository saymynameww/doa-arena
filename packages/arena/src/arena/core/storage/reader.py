"""从普通文件恢复结果，不依赖服务内存或索引。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal, cast

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
    with np.load(directory / "results.npz", allow_pickle=False) as raw:
        labels = [key[:-11] for key in raw.files if key.endswith("__estimates")]
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
