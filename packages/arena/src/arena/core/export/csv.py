"""CSV 导出。"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from ..metrics.summary import algorithm_labels, point_metrics
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
    algo_labels = algorithm_labels(result)

    # 准备表头
    headers = ["point_idx", "sweep_value"]

    for label in algo_labels:
        headers.extend(
            [
                f"{label}_rmse",
                f"{label}_success_rate",
                f"{label}_avg_time_ms",
            ]
        )

    # 写入 CSV
    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(headers)

        for point in result.points:
            row: list[Any] = [point.point_idx, point.sweep_value]

            for label in algo_labels:
                metrics = point_metrics(result, point, label)
                row.extend([metrics["rmse_mean"], metrics["success_rate"], metrics["avg_time_ms"]])

            writer.writerow(row)
