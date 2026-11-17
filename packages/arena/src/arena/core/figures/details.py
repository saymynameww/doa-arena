"""面向结果页的统一表格数据；数值统计仍在核心执行。"""

from typing import Any

import numpy as np

from arena_api import kit

from ..metrics.summary import algorithm_labels, point_metrics
from ..runner.results import ExperimentResult
from .presentation import build_figures


def result_details(result: ExperimentResult) -> dict[str, Any]:
    """提供图表联动的逐点指标、有效样本、错误和复现信息。"""
    figures = build_figures(result)
    from ..plugins import resolve_plugin

    bounds: list[Any] = []
    for fig in figures.values():
        for trace in fig.data:
            if str(trace.name).startswith("CRB"):
                bounds = list(trace.y)
    rows = []
    definitions: dict[str, dict[str, Any]] = {}
    directions: dict[str, bool] = {}
    for i, point in enumerate(result.points):
        for label in algorithm_labels(result):
            summary = point_metrics(result, point, label)
            values = summary["metric_values"]
            metrics = {}
            for key, item in values.items():
                value = item["value"]
                cls = resolve_plugin(
                    "metric", key, result.config.get("metrics", {}).get("origins", {}).get(key)
                )
                # FR-RES-02：表格同时列出两个统计量；耗时曲线仍遵循配置 stat。
                variants = (
                    [
                        ("time_mean", "平均耗时", (item.get("extra") or {}).get("mean")),
                        ("time_median", "中位耗时", (item.get("extra") or {}).get("median")),
                    ]
                    if key == "time"
                    else [(key, cls.name, value)]
                )
                for column_key, column_label, column_value in variants:
                    metrics[column_key] = (
                        column_value * 100
                        if cls.unit == "%" and column_value is not None
                        else column_value
                    )
                    definitions[column_key] = {
                        "key": column_key,
                        "label": column_label,
                        "unit": cls.unit,
                        "metric": key,
                    }
                    directions[column_key] = cls.higher_is_better
            rmse = values.get("rmse", {}).get("value")
            bound = bounds[i] if i < len(bounds) else None
            errors = [t.errors[label] for t in point.trials if label in t.errors]
            row = {
                "point": point.point_idx,
                "x": point.sweep_value,
                "algorithm": label,
                "metrics": metrics,
                "n_used": values.get("rmse", {}).get("n_used", 0),
                "n_total": len(point.trials),
                "errors": errors,
                "crb": bound,
                "efficiency": rmse / bound
                if rmse is not None and bound and np.isfinite(bound)
                else None,
            }
            from .identity import algorithm_style

            row["style"] = algorithm_style(algorithm_labels(result).index(label))
            if result.config.get("type") == "single" and point.trials:
                trial = point.trials[0]
                estimate = trial.estimates.get(label)
                truth = trial.truth_angles
                row["angles"] = estimate.angles.tolist() if estimate is not None else []
                if estimate is not None and truth is not None:
                    pairs, _ = kit.hungarian_matching(estimate.angles, truth)
                    row["max_error"] = max(
                        (abs(float(estimate.angles[a] - truth[b])) for a, b in pairs), default=None
                    )
            rows.append(row)
    columns = []
    for name in dict.fromkeys(k for row in rows for k in row["metrics"]):
        columns.append(definitions[name])
        for point in result.points:
            candidates = [r for r in rows if r["point"] == point.point_idx]
            finite = [r["metrics"].get(name) for r in candidates]
            finite = [v for v in finite if v is not None and np.isfinite(v)]
            if finite:
                best = max(finite) if directions[name] else min(finite)
                for row in candidates:
                    if row["metrics"].get(name) == best:
                        row.setdefault("best", []).append(name)

    def clean(value: Any) -> Any:
        if isinstance(value, dict):
            return {k: clean(v) for k, v in value.items()}
        if isinstance(value, list):
            return [clean(v) for v in value]
        if isinstance(value, float | np.floating) and not np.isfinite(value):
            return None
        return value

    return clean({"rows": rows, "columns": columns, "metadata": result.metadata})
