"""MATLAB 导出。"""

from __future__ import annotations

from pathlib import Path

import numpy as np

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
    algo_labels = []
    if result.points and result.points[0].trials:
        first_trial = result.points[0].trials[0]
        algo_labels = list(first_trial.estimates.keys())

    # 扫描值
    sweep_values = np.array([p.sweep_value for p in result.points])

    # 每个算法的数据
    data = {
        "sweep_values": sweep_values,
        "point_indices": np.array([p.point_idx for p in result.points]),
    }

    for label in algo_labels:
        # 收集该算法的所有估计
        rmse_values = []
        success_rates = []
        avg_times = []

        for point in result.points:
            from ..metrics import compute_metrics

            estimates = [
                trial.estimates[label]
                for trial in point.trials
                if label in trial.estimates
            ]

            truth_angles = np.array([-10.0, 10.0])  # 简化
            metrics = compute_metrics(estimates, truth_angles)

            rmse_values.append(metrics.get("rmse_mean", np.nan))
            success_rates.append(metrics.get("success_rate", np.nan))

            times = [
                trial.times_ms.get(label, np.nan)
                for trial in point.trials
                if label in trial.times_ms
            ]
            avg_times.append(np.nanmean(times))

        # 存储
        safe_label = label.replace(" ", "_").replace("-", "_")
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
