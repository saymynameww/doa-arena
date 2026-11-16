"""LaTeX 表格导出。"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from ..metrics.summary import algorithm_labels, point_metrics
from ..runner.results import ExperimentResult


def export_to_latex(
    result: ExperimentResult,
    output_path: Path | str,
    caption: str = "实验结果",
    label: str = "tab:results",
) -> None:
    """导出实验结果为 LaTeX 表格。

    Args:
        result: 实验结果
        output_path: 输出路径
        caption: 表格标题
        label: 表格标签
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 收集算法标签
    algo_labels = algorithm_labels(result)

    # 开始写入
    lines = []

    # 表格开始
    lines.append(r"\begin{table}[htbp]")
    lines.append(r"  \centering")
    lines.append(f"  \\caption{{{caption}}}")
    lines.append(f"  \\label{{{label}}}")

    # 列定义
    col_spec = "c" + "|cc" * len(algo_labels)
    lines.append(f"  \\begin{{tabular}}{{{col_spec}}}")
    lines.append(r"    \hline")

    # 表头
    header = ["扫描值"]
    for label in algo_labels:
        header.append(f"\\multicolumn{{2}}{{c}}{{{label}}}")

    lines.append("    " + " & ".join(header) + r" \\")
    lines.append(r"    \hline")

    # 子表头（RMSE 和成功率）
    subheader = [""]
    for _ in algo_labels:
        subheader.extend(["RMSE", "成功率"])

    lines.append("    " + " & ".join(subheader) + r" \\")
    lines.append(r"    \hline")

    # 数据行
    for point in result.points:
        row = [f"{point.sweep_value:g}" if point.sweep_value is not None else "--"]

        for label in algo_labels:
            metrics = point_metrics(result, point, label)

            # RMSE
            rmse = metrics.get("rmse_mean", np.nan)
            row.append(f"{rmse:.3f}" if not np.isnan(rmse) else "--")

            # 成功率（百分比）
            success_rate = metrics.get("success_rate", np.nan)
            if not np.isnan(success_rate):
                row.append(f"{success_rate * 100:.1f}\\%")
            else:
                row.append("--")

        lines.append("    " + " & ".join(row) + r" \\")

    # 表格结束
    lines.append(r"    \hline")
    lines.append(r"  \end{tabular}")
    lines.append(r"\end{table}")

    # 写入文件
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
