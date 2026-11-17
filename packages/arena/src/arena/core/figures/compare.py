"""多实验对比图的共享导出构建器。"""

from pathlib import Path
from typing import Any

import plotly.graph_objects as go

from ..runner.results import ExperimentResult
from .presentation import build_figures


def comparison_figure(results: list[ExperimentResult], metric: str, log: bool = False) -> go.Figure:
    """按指标标识匹配曲线，算法用颜色，实验用线型和标记。"""
    if not 2 <= len(results) <= 4:
        raise ValueError("请选择 2–4 个参数扫描实验")
    if any(r.config.get("type") != "sweep" for r in results):
        raise ValueError("只有参数扫描实验可以对比")
    if len({(r.config.get("sweep") or {}).get("path") for r in results}) != 1:
        raise ValueError("选中的实验扫描变量不同")
    colors = ["#1677ff", "#fa8c16", "#13a86b", "#8b5cf6", "#e34b72", "#0891b2"]
    labels: list[str] = []
    output = go.Figure()
    for i, result in enumerate(results):
        figure = next(
            (
                f
                for f in build_figures(result).values()
                if (f.layout.meta or {}).get("metric") == metric
            ),
            None,
        )
        if figure is None:
            continue
        if not output.data:
            output.update_layout(figure.layout)
        for trace in figure.data:
            label = str(trace.name)
            if label not in labels:
                labels.append(label)
            trace.name = f"{label} · {result.config.get('name', i + 1)}"
            trace.line.color = (
                "#334155" if label.startswith("CRB") else colors[labels.index(label) % len(colors)]
            )
            trace.line.dash = ["solid", "dash", "dot", "dashdot"][i]
            trace.marker.symbol = ["circle", "square", "diamond", "triangle-up"][i]
            output.add_trace(trace)
    if not output.data:
        raise ValueError("这些实验未保存所选指标")
    output.update_yaxes(type="log" if log else "linear")
    output.update_layout(legend={"orientation": "h", "y": -0.3}, margin={"b": 130})
    return output


def export_comparison(payload: dict[str, Any]) -> dict[str, str]:
    """导出到第一个实验的 exports 目录，不改变原始数据。"""
    from datetime import datetime
    from typing import cast

    from ..storage.reader import read_result
    from .export import ExportFormat, export_figure

    fmt = payload["format"]
    if fmt not in {"png", "svg", "pdf", "html"}:
        raise ValueError("对比图支持 PNG、SVG、PDF、HTML")
    directories = [Path(p) for p in payload["directories"]]
    figure = comparison_figure(
        [read_result(p) for p in directories], payload["metric"], payload.get("log", False)
    )
    target = directories[0] / "exports" / f"comparison_{datetime.now():%Y%m%d_%H%M%S_%f}.{fmt}"
    export_figure(figure, target, format=cast(ExportFormat, fmt))
    return {"path": str(target)}
