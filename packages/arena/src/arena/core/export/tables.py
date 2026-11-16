"""各导出格式共享实际指标表和算法顺序。"""

from typing import Any

from ..metrics.summary import algorithm_labels, point_metrics
from ..runner.results import ExperimentResult


def export_summary(result: ExperimentResult) -> dict[str, Any]:
    """生成导出使用的完整指标表，恢复的结果优先使用保存汇总。"""
    if result.saved_summary is not None:
        return result.saved_summary
    labels = algorithm_labels(result)
    points = [
        {"algorithms": {label: point_metrics(result, p, label) for label in labels}}
        for p in result.points
    ]
    names = list(points[0]["algorithms"][labels[0]]["metric_values"]) if points and labels else []
    metrics = {
        name: {
            field: [
                [p["algorithms"][label]["metric_values"][name][field] for label in labels]
                for p in points
            ]
            for field in ("value", "n_used")
        }
        for name in names
    }
    crb = None
    if "scenario" in result.config and "crb" in result.config.get("metrics", {}).get("include", []):
        import numpy as np

        from ..metrics.sourcewise import sourcewise_arrays

        arrays = sourcewise_arrays(result, labels)
        if "crb_per_source" in arrays:
            crb = {"value": np.sqrt(np.mean(arrays["crb_per_source"] ** 2, axis=1)).tolist()}
    return {"metrics": metrics, "points": points, "crb": crb}


def metric_table(result: ExperimentResult, metric: str) -> tuple[list[str], list[list[Any]]]:
    """每行一个扫描点，每列一个算法，RMSE 附加保存的 CRB。"""
    summary = export_summary(result)
    if metric not in summary["metrics"]:
        raise ValueError(f"实验未计算指标 {metric}，请先重新计算指标")
    sweep = result.config.get("sweep") or {}
    axis = sweep.get("label") or sweep.get("path") or "实验点"
    if sweep.get("unit"):
        axis += " (" + sweep["unit"] + ")"
    headers = [axis, *algorithm_labels(result)]
    with_crb = metric == "rmse" and summary.get("crb") is not None
    if with_crb:
        headers.append("CRB")
    rows = []
    for pi, point in enumerate(result.points):
        row = [
            point.sweep_value if point.sweep_value is not None else point.point_idx,
            *summary["metrics"][metric]["value"][pi],
        ]
        if with_crb:
            row.append(summary["crb"]["value"][pi])
        rows.append(row)
    return headers, rows
