"""图表生成模块。

使用 Plotly 生成交互式图表，支持静态导出。
"""

import plotly.graph_objects as go

from ..runner.results import ExperimentResult
from .charts import ChartGenerator, create_rmse_curve, create_success_rate_curve
from .export import export_figure

__all__ = [
    "build",
    "ChartGenerator",
    "create_rmse_curve",
    "create_success_rate_curve",
    "export_figure",
]


def build(result: ExperimentResult, metric: str) -> go.Figure:
    """构建与网页相同的指定指标图，返回可继续编辑的 Plotly Figure。"""
    from ..plugins import resolve_plugin
    from .presentation import build_figures

    name = "resolution_prob" if metric == "resolution" else metric
    cls = resolve_plugin(
        "metric", name, result.config.get("metrics", {}).get("origins", {}).get(name)
    )
    title = "运行时间" if name == "time" else cls.name
    charts = build_figures(result)
    if title not in charts:
        raise ValueError(f"实验未计算指标 {name}，请先重新计算指标")
    return charts[title]
