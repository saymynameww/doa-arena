"""MATLAB 导出。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from ..metrics.summary import algorithm_labels, point_metrics
from ..runner.results import ExperimentResult


def export_to_mat(result: ExperimentResult, output_path: Path | str) -> None:
    """导出实验结果为 MATLAB .mat 文件。

    Args:
        result: 实验结果
        output_path: 输出路径

    Raises:
        ImportError: scipy 未安装
    """
    try:
        from scipy.io import savemat
    except ImportError:
        raise ImportError("MATLAB 导出需要 scipy。安装：pip install scipy")

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 收集数据
    algo_labels = algorithm_labels(result)

    # 扫描值
    sweep_values = np.array(
        [p.sweep_value if p.sweep_value is not None else np.nan for p in result.points]
    )

    # 每个算法的数据
    data: dict[str, Any] = {
        "sweep_values": sweep_values,
        "point_indices": np.array([p.point_idx for p in result.points]),
    }

    for index, label in enumerate(algo_labels):
        # 收集该算法的所有估计
        rmse_values = []
        success_rates = []
        avg_times = []

        for point in result.points:
            metrics = point_metrics(result, point, label)
            rmse_values.append(metrics["rmse_mean"])
            success_rates.append(metrics["success_rate"])
            avg_times.append(metrics["avg_time_ms"])

        # 存储
        safe_label = label.replace(" ", "_").replace("-", "_")
        if not safe_label.isascii() or not safe_label.isidentifier() or len(safe_label) > 40:
            safe_label = f"algorithm_{index}"
        data[f"{safe_label}_rmse"] = np.array(rmse_values)
        data[f"{safe_label}_success_rate"] = np.array(success_rates)
        data[f"{safe_label}_avg_time_ms"] = np.array(avg_times)

    # 元信息
    data["metadata"] = {
        "experiment_name": result.config.get("name", "Unnamed"),
        "num_trials": result.config.get("trials", 0),
        "algorithms": algo_labels,
    }

    # 保存
    savemat(str(output_path), data, oned_as="column")
