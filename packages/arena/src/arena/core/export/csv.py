"""数据格式 4.7 节：一个指标一张 UTF-8 BOM 表。"""

import csv
from pathlib import Path

import numpy as np

from ..runner.results import ExperimentResult
from .tables import metric_table


def export_to_csv(result: ExperimentResult, output_path: Path | str, metric: str = "rmse") -> None:
    """导出指定指标，缺失值写空单元格。"""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    headers, rows = metric_table(result, metric)
    with output_path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.writer(stream)
        writer.writerow(headers)
        for row in rows:
            writer.writerow(
                [
                    value
                    if value is not None and (not isinstance(value, float) or np.isfinite(value))
                    else ""
                    for value in row
                ]
            )
