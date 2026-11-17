"""脚本和隔离服务共享的导出入口。"""

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Literal, cast

from ..storage.reader import read_result
from ..storage.writer import ResultWriter
from .csv import export_to_csv
from .latex import export_to_latex
from .matlab import export_to_mat


def export_result(
    directory: Path,
    fmt: str,
    metric: str = "rmse",
    chart: str | None = None,
    style: str = "web",
    log: bool = False,
) -> Path:
    """输出带时间戳的文件，图表按用户当前选择导出。"""
    if fmt not in {"json", "npz", "csv", "mat", "tex", "html", "png", "svg", "pdf", "py"}:
        raise ValueError("不支持的导出格式")
    result = read_result(directory)
    target = directory / "exports"
    target.mkdir(exist_ok=True)
    output = target / ("experiment_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f") + "." + fmt)
    if fmt == "json":
        ResultWriter(directory)._write_json(
            output,
            {"config": result.config, "metadata": result.metadata, "summary": result.saved_summary},
        )
    elif fmt == "npz":
        shutil.copyfile(directory / "results.npz", output)
    elif fmt == "csv":
        export_to_csv(result, output, metric=metric)
    elif fmt == "tex":
        export_to_latex(result, output, metric=metric)
    elif fmt == "mat":
        export_to_mat(result, output)
    elif fmt == "html" and chart is None:
        from ..reports.html import generate_html_report

        generate_html_report(result, output)
    elif fmt in {"png", "svg", "pdf", "html"}:
        from ..figures.export import export_figure
        from ..figures.presentation import build_figures

        figures = build_figures(result)
        title = chart or next(iter(figures), None)
        if title not in figures:
            raise ValueError("指定图表不存在，请刷新图表列表")
        figure = figures[title]
        figure.update_layout(
            font={"size": 12 if style == "web" else 16}, height=360 if style == "single" else 500
        )
        if log:
            figure.update_yaxes(type="log")
        export_figure(figure, output, format=cast(Literal["png", "svg", "pdf", "html"], fmt))
    elif fmt == "py":
        output.write_text(
            "import arena\nimport json\nconfig = json.loads("
            + repr(json.dumps(result.config, ensure_ascii=False))
            + ")\nif __name__ == '__main__':\n    result = arena.run(config)\n",
            encoding="utf-8",
        )
    return output
