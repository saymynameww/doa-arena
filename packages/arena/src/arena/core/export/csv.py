"""CSV 导出。"""

from __future__ import annotations

import csv
from pathlib import Path

import numpy as np

from ..runner.results import ExperimentResult


def export_to_csv(result: ExperimentResult, output_path: Path | str) -> None:
    """导出实验结果为 CSV。

    Args:
        result: 实验结果
        output_path: 输出路径
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 收集算法标签
    algo_labels = []
    if result.points and result.points[0].trials:
        first_trial = result.points[0].trials[0]
        algo_labels = list(first_trial.estimates.keys())

    # 准备表头
    headers = ["point_idx", "sweep_value"]

    for label in algo_labels:
        headers.extend([
            f"{label}_rmse",
            f"{label}_success_rate",
            f"{label}_avg_time_ms",
        ])

    # 写入 CSV
    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(headers)

        for point in result.points:
            row = [point.point_idx, point.sweep_value]

            for label in algo_labels:
                # 计算指标
                from ..metrics import compute_metrics

                estimates = [
                    trial.estimates[label]
                    for trial in point.trials
                    if label in trial.estimates
                ]

                truth_angles = np.array([-10.0, 10.0])  # 简化
                metrics = compute_metrics(estimates, truth_angles)

                # RMSE
                row.append(metrics.get("rmse_mean", ""))

                # 成功率
                row.append(metrics.get("success_rate", ""))

                # 平均时间
                times = [
                    trial.times_ms.get(label, np.nan)
                    for trial in point.trials
                    if label in trial.times_ms
                ]
                avg_time = np.nanmean(times) if times else ""
                row.append(avg_time)

            writer.writerow(row)
