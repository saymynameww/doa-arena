"""图表导出。

支持导出为 PNG、PDF、SVG 等静态格式。
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Literal

import plotly.graph_objects as go

logger = logging.getLogger(__name__)

ExportFormat = Literal["png", "pdf", "svg", "html"]


def export_figure(
    fig: go.Figure,
    path: Path | str,
    format: ExportFormat = "png",
    width: int | None = None,
    height: int | None = None,
) -> None:
    """导出图表为静态文件。

    Args:
        fig: Plotly 图表
        path: 输出路径
        format: 导出格式（png/pdf/svg/html）
        width: 宽度（像素），None 使用图表默认值
        height: 高度（像素），None 使用图表默认值

    Raises:
        ImportError: kaleido 未安装（png/pdf/svg 需要）
        ValueError: 不支持的格式
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    if format == "html":
        # HTML 导出不需要 kaleido
        fig.write_html(str(path))
        logger.info(f"导出 HTML: {path}")
        return

    # 静态格式需要 kaleido
    try:
        import kaleido  # noqa: F401
    except ImportError:
        raise ImportError(
            "静态图表导出需要 kaleido。\n"
            "安装：pip install kaleido\n"
            "或使用 format='html' 导出交互式 HTML。"
        )

    # 导出静态图
    if format == "png":
        # FR-RES-07：以网页 96 dpi 的逻辑尺寸输出 300 dpi 等效像素。
        fig.write_image(str(path), format="png", width=width, height=height, scale=300 / 96)
    elif format == "pdf":
        fig.write_image(str(path), format="pdf", width=width, height=height)
    elif format == "svg":
        fig.write_image(str(path), format="svg", width=width, height=height)
    else:
        raise ValueError(f"不支持的格式: {format}")

    logger.info(f"导出 {format.upper()}: {path}")


def export_all_charts(
    charts: dict[str, go.Figure],
    output_dir: Path | str,
    format: ExportFormat = "png",
) -> None:
    """批量导出图表。

    Args:
        charts: 图表字典 {name: figure}
        output_dir: 输出目录
        format: 导出格式
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    for name, fig in charts.items():
        filename = f"{name}.{format}"
        export_figure(fig, output_dir / filename, format=format)

    logger.info(f"导出 {len(charts)} 个图表到 {output_dir}")
