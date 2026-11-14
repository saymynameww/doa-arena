"""结果写入器。

按架构文档第 5.8 节，使用原子写入（临时文件+重命名）。
"""

from __future__ import annotations

import json
import tempfile
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
        self._write_json(self.output_dir / "config.json", result.config)

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
        # 收集所有算法的估计结果
        algo_labels = []
        if result.points and result.points[0].trials:
            first_trial = result.points[0].trials[0]
            algo_labels = list(first_trial.estimates.keys())

        if not algo_labels:
            return

        # 准备数据结构
        num_points = len(result.points)
        num_trials = len(result.points[0].trials) if result.points else 0

        data = {}

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
            for i, est in enumerate(estimates_list):
                point_idx = i // num_trials
                trial_idx = i % num_trials
                if len(est) > 0:
                    estimates_padded[point_idx, trial_idx, : len(est)] = est

            # 存储
            data[f"{label}__estimates"] = estimates_padded
            data[f"{label}__times_ms"] = np.array(times_list).reshape(
                num_points, num_trials
            )
            data[f"{label}__failed"] = np.array(failed_list).reshape(
                num_points, num_trials
            )

        # 写入 npz
        self._write_npz(self.output_dir / "results.npz", data)

    def _write_summary(self, result: ExperimentResult) -> None:
        """写入汇总统计。

        Args:
            result: 实验结果
        """
        # 获取真实角度（简化：从配置读取）
        truth_angles = np.array([-10.0, 10.0])  # 简化版

        summary = {
            "algorithms": [],
            "points": [],
        }

        # 收集算法名
        if result.points and result.points[0].trials:
            first_trial = result.points[0].trials[0]
            algo_labels = list(first_trial.estimates.keys())
        else:
            algo_labels = []

        # 每个扫描点
        for point in result.points:
            point_summary = {
                "point_idx": point.point_idx,
                "sweep_value": point.sweep_value,
                "algorithms": {},
            }

            # 每个算法
            for label in algo_labels:
                # 收集该算法该点的所有估计
                estimates = []
                for trial in point.trials:
                    if label in trial.estimates:
                        estimates.append(trial.estimates[label])

                if not estimates:
                    continue

                # 计算指标
                metrics = compute_metrics(estimates, truth_angles)

                point_summary["algorithms"][label] = metrics

            summary["points"].append(point_summary)

        # 写入
        self._write_json(self.output_dir / "summary.json", summary)

    def _write_json(self, path: Path, data: Any) -> None:
        """原子写入 JSON。

        Args:
            path: 文件路径
            data: 数据
        """
        # 写入临时文件
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            delete=False,
            suffix=".tmp",
        ) as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            temp_path = f.name

        # 原子重命名
        Path(temp_path).replace(path)

    def _write_npz(self, path: Path, data: dict[str, np.ndarray]) -> None:
        """原子写入 npz。

        Args:
            path: 文件路径
            data: 数据字典
        """
        # 写入临时文件
        with tempfile.NamedTemporaryFile(
            dir=path.parent,
            delete=False,
            suffix=".tmp",
        ) as f:
            np.savez(f, **data)
            temp_path = f.name

        # 原子重命名
        Path(temp_path).replace(path)
