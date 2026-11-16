"""图表入口：Web、脚本与导出使用同一构建器。"""

from __future__ import annotations

import plotly.graph_objects as go

from ..runner.results import ExperimentResult
from .presentation import build_figures


class ChartGenerator:
    """保留脚本图表 API，底层统一到真实结果模型。"""

    def __init__(self, result: ExperimentResult) -> None:
        self.result = result

    def create_all_charts(self) -> dict[str, go.Figure]:
        """返回所有适用图表。"""
        aliases = {
            "RMSE": "rmse_curve",
            "成功率": "success_rate_curve",
            "运行时间": "time_curve",
            "空间谱": "estimates_scatter",
            "估计分布": "estimates_distribution",
        }
        return {aliases.get(key, key): fig for key, fig in build_figures(self.result).items()}

    def create_rmse_curve(self) -> go.Figure:
        """创建 RMSE 曲线。"""
        return build_figures(self.result)["RMSE"]

    def create_success_rate_curve(self) -> go.Figure:
        """创建成功率曲线。"""
        return build_figures(self.result)["成功率"]

    def create_time_curve(self) -> go.Figure:
        """创建计时曲线。"""
        return build_figures(self.result)["运行时间"]

    def create_estimates_scatter(self) -> go.Figure:
        """创建真实谱和估计标记图。"""
        return build_figures(self.result)["空间谱"]


def create_rmse_curve(result: ExperimentResult) -> go.Figure:
    """创建 RMSE 曲线。"""
    return ChartGenerator(result).create_rmse_curve()


def create_success_rate_curve(result: ExperimentResult) -> go.Figure:
    """创建成功率曲线。"""
    return ChartGenerator(result).create_success_rate_curve()
