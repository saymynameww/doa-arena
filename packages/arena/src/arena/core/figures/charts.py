"""图表生成核心。

使用 Plotly 生成交互式图表。
"""

from __future__ import annotations

from typing import Any

import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from ..runner.results import ExperimentResult


class ChartGenerator:
    """图表生成器。

    生成实验结果的可视化图表。
    """

    def __init__(self, result: ExperimentResult) -> None:
        """初始化。

        Args:
            result: 实验结果
        """
        self.result = result

    def create_all_charts(self) -> dict[str, go.Figure]:
        """生成所有图表。

        Returns:
            图表字典 {name: figure}
        """
        charts = {}

        # RMSE 曲线
        if self._is_sweep():
            charts["rmse_curve"] = self.create_rmse_curve()
            charts["success_rate_curve"] = self.create_success_rate_curve()
            charts["time_curve"] = self.create_time_curve()

        # 估计散点图（单次实验）
        if self._is_single():
            charts["estimates_scatter"] = self.create_estimates_scatter()

        return charts

    def create_rmse_curve(self) -> go.Figure:
        """创建 RMSE 曲线。

        Returns:
            Plotly 图表
        """
        fig = go.Figure()

        sweep_values = [p.sweep_value for p in self.result.points]
        algo_labels = self._get_algorithm_labels()

        for label in algo_labels:
            rmse_values = []

            for point in self.result.points:
                # 计算该算法该点的 RMSE
                rmse = self._compute_rmse_for_point(point, label)
                rmse_values.append(rmse)

            fig.add_trace(
                go.Scatter(
                    x=sweep_values,
                    y=rmse_values,
                    mode="lines+markers",
                    name=label,
                    line=dict(width=2),
                    marker=dict(size=8),
                )
            )

        # 布局
        config = self.result.config
        sweep_config = config.get("sweep", {})

        fig.update_layout(
            title="RMSE vs 扫描变量",
            xaxis_title=f"{sweep_config.get('label', '扫描变量')} ({sweep_config.get('unit', '')})",
            yaxis_title="RMSE (°)",
            hovermode="x unified",
            template="plotly_white",
            width=800,
            height=500,
        )

        return fig

    def create_success_rate_curve(self) -> go.Figure:
        """创建成功率曲线。

        Returns:
            Plotly 图表
        """
        fig = go.Figure()

        sweep_values = [p.sweep_value for p in self.result.points]
        algo_labels = self._get_algorithm_labels()

        for label in algo_labels:
            success_rates = []

            for point in self.result.points:
                # 计算该算法该点的成功率
                rate = self._compute_success_rate_for_point(point, label)
                success_rates.append(rate * 100)  # 转为百分比

            fig.add_trace(
                go.Scatter(
                    x=sweep_values,
                    y=success_rates,
                    mode="lines+markers",
                    name=label,
                    line=dict(width=2),
                    marker=dict(size=8),
                )
            )

        # 布局
        config = self.result.config
        sweep_config = config.get("sweep", {})

        fig.update_layout(
            title="成功率 vs 扫描变量",
            xaxis_title=f"{sweep_config.get('label', '扫描变量')} ({sweep_config.get('unit', '')})",
            yaxis_title="成功率 (%)",
            hovermode="x unified",
            template="plotly_white",
            width=800,
            height=500,
            yaxis=dict(range=[0, 105]),  # 0-100%
        )

        return fig

    def create_time_curve(self) -> go.Figure:
        """创建计算时间曲线。

        Returns:
            Plotly 图表
        """
        fig = go.Figure()

        sweep_values = [p.sweep_value for p in self.result.points]
        algo_labels = self._get_algorithm_labels()

        for label in algo_labels:
            avg_times = []

            for point in self.result.points:
                # 计算该算法该点的平均时间
                times = [
                    trial.times_ms.get(label, np.nan)
                    for trial in point.trials
                    if label in trial.times_ms
                ]
                avg_times.append(np.nanmean(times))

            fig.add_trace(
                go.Scatter(
                    x=sweep_values,
                    y=avg_times,
                    mode="lines+markers",
                    name=label,
                    line=dict(width=2),
                    marker=dict(size=8),
                )
            )

        # 布局
        config = self.result.config
        sweep_config = config.get("sweep", {})

        fig.update_layout(
            title="计算时间 vs 扫描变量",
            xaxis_title=f"{sweep_config.get('label', '扫描变量')} ({sweep_config.get('unit', '')})",
            yaxis_title="平均时间 (ms)",
            hovermode="x unified",
            template="plotly_white",
            width=800,
            height=500,
        )

        return fig

    def create_estimates_scatter(self) -> go.Figure:
        """创建估计散点图（单次实验）。

        Returns:
            Plotly 图表
        """
        fig = go.Figure()

        # 真值
        truth_angles = np.array([-10.0, 10.0])  # 简化：从配置读取

        # 算法估计
        trial = self.result.points[0].trials[0]

        for label, estimate in trial.estimates.items():
            fig.add_trace(
                go.Scatter(
                    x=estimate.angles,
                    y=[0] * len(estimate.angles),
                    mode="markers",
                    name=label,
                    marker=dict(size=12, symbol="x"),
                )
            )

        # 真值
        fig.add_trace(
            go.Scatter(
                x=truth_angles,
                y=[0] * len(truth_angles),
                mode="markers",
                name="真值",
                marker=dict(size=15, symbol="circle", color="red"),
            )
        )

        fig.update_layout(
            title="估计角度",
            xaxis_title="角度 (°)",
            yaxis=dict(visible=False),
            hovermode="closest",
            template="plotly_white",
            width=800,
            height=300,
        )

        return fig

    def _is_sweep(self) -> bool:
        """是否为扫描实验。"""
        return len(self.result.points) > 1

    def _is_single(self) -> bool:
        """是否为单次实验。"""
        return len(self.result.points) == 1 and len(self.result.points[0].trials) == 1

    def _get_algorithm_labels(self) -> list[str]:
        """获取算法标签列表。"""
        if not self.result.points or not self.result.points[0].trials:
            return []

        first_trial = self.result.points[0].trials[0]
        return list(first_trial.estimates.keys())

    def _compute_rmse_for_point(self, point, label: str) -> float:
        """计算某算法某点的 RMSE。"""
        from ..metrics import compute_metrics

        # 收集该算法的所有估计
        estimates = []
        for trial in point.trials:
            if label in trial.estimates:
                estimates.append(trial.estimates[label])

        if not estimates:
            return np.nan

        # 计算指标
        truth_angles = np.array([-10.0, 10.0])  # 简化
        metrics = compute_metrics(estimates, truth_angles)

        return metrics.get("rmse_mean", np.nan)

    def _compute_success_rate_for_point(self, point, label: str) -> float:
        """计算某算法某点的成功率。"""
        from ..metrics import compute_metrics

        # 收集该算法的所有估计
        estimates = []
        for trial in point.trials:
            if label in trial.estimates:
                estimates.append(trial.estimates[label])

        if not estimates:
            return np.nan

        # 计算指标
        truth_angles = np.array([-10.0, 10.0])  # 简化
        metrics = compute_metrics(estimates, truth_angles)

        return metrics.get("success_rate", np.nan)


def create_rmse_curve(result: ExperimentResult) -> go.Figure:
    """快捷函数：创建 RMSE 曲线。

    Args:
        result: 实验结果

    Returns:
        Plotly 图表
    """
    gen = ChartGenerator(result)
    return gen.create_rmse_curve()


def create_success_rate_curve(result: ExperimentResult) -> go.Figure:
    """快捷函数：创建成功率曲线。

    Args:
        result: 实验结果

    Returns:
        Plotly 图表
    """
    gen = ChartGenerator(result)
    return gen.create_success_rate_curve()
