"""数据格式 4.7 节的 MATLAB arena 结构体。"""

import logging
from pathlib import Path

import numpy as np

from ..metrics.summary import algorithm_labels
from ..runner.results import ExperimentResult
from ..storage.contract import standard_arrays
from .tables import export_summary
from .utf16_mat import write_mat


def export_to_mat(result: ExperimentResult, output_path: Path | str) -> None:
    """导出标准维度、中文 cell 标签和 NaN，不创建不安全的变量名。"""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    labels = algorithm_labels(result)
    summary = export_summary(result)
    arrays = standard_arrays(result, labels, summary)
    sweep = result.config.get("sweep") or {}
    data = {
        "name": result.config.get("name", ""),
        "id": result.metadata.get("id", result.metadata.get("experiment_id", "")),
        "sweep": {
            "path": sweep.get("path") or "",
            "label": sweep.get("label") or "",
            "unit": sweep.get("unit") or "",
            "values": arrays["sweep_values"],
        },
        "algorithms": np.asarray(labels, dtype=object).reshape(-1, 1),
        "metric": {
            key: np.asarray(value["value"], dtype=float)
            for key, value in summary["metrics"].items()
        },
        "metric_n_used": {
            key: np.asarray(value["n_used"], dtype=float)
            for key, value in summary["metrics"].items()
        },
        "crb": arrays.get("crb", np.array([])),
        "truth": arrays["truth"],
        "estimates": arrays.get("estimates", np.array([])),
        "status": arrays.get("status", np.array([])).astype(float),
    }
    if data["estimates"].nbytes >= 2**31:
        logging.getLogger(__name__).warning("逐次估计超过 MAT v5 的 2 GB 限制，仅导出指标")
        data["estimates"] = np.array([])
    write_mat(output_path, data)
