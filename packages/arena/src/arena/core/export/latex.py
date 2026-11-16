"""数据格式 4.7 节：booktabs 指标表与特殊字符转义。"""

from pathlib import Path

import numpy as np

from ..metrics.summary import algorithm_labels
from ..runner.results import ExperimentResult
from .tables import metric_table


def escape_latex(value: str) -> str:
    """逐字符转义，避免转义生成的反斜杠再次被处理。"""
    mapping = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    return "".join(mapping.get(char, char) for char in value)


def export_to_latex(
    result: ExperimentResult,
    output_path: Path | str,
    caption: str = "实验结果",
    label: str = "tab:results",
    *,
    metric: str = "rmse",
    bold_best: bool = False,
) -> None:
    """导出 tabular；caption/label 为旧版兼容参数，不生成浮动体。"""
    headers, rows = metric_table(result, metric)
    lines = [
        r"\begin{tabular}{" + "r" * len(headers) + "}",
        r"\toprule",
        " & ".join(escape_latex(x) for x in headers) + r" \\",
        r"\midrule",
    ]
    from ..plugins import resolve_plugin

    cls = resolve_plugin(
        "metric", metric, result.config.get("metrics", {}).get("origins", {}).get(metric)
    )
    for row in rows:
        candidates = [
            v
            for v in row[1 : 1 + len(algorithm_labels(result))]
            if v is not None and np.isfinite(v)
        ]
        best = (
            (max(candidates) if cls.higher_is_better else min(candidates)) if candidates else None
        )
        cells = []
        for i, value in enumerate(row):
            text = "--" if value is None or not np.isfinite(value) else f"{value:.3f}"
            if (
                bold_best
                and 0 < i <= len(algorithm_labels(result))
                and best is not None
                and value == best
            ):
                text = r"\textbf{" + text + "}"
            cells.append(text)
        lines.append(" & ".join(cells) + r" \\")
    lines.extend([r"\bottomrule", r"\end{tabular}"])
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
