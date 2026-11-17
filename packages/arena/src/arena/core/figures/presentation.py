"""网页、脚本和导出共用的结果图表。"""

from __future__ import annotations

from typing import cast

import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from arena_api import kit

from ..metrics.summary import algorithm_labels, point_metrics
from ..runner.results import ExperimentResult, TrialResult


def build_figures(result: ExperimentResult) -> dict[str, go.Figure]:
    """按实验类型生成真实空间谱、匹配分布及指标曲线。"""
    figures: dict[str, go.Figure] = {}
    if not result.points or not result.points[0].trials:
        return figures
    labels = algorithm_labels(result)
    first = result.points[0].trials[0]
    fallback = np.asarray(result.config["scenario"]["sources"]["angles"].get("values") or [])

    def truth(trial: TrialResult) -> np.ndarray:
        return trial.truth_angles if trial.truth_angles is not None else fallback

    palette = ["#1677ff", "#fa8c16", "#13a86b", "#8b5cf6", "#e34b72", "#0891b2"]
    if result.config.get("type") == "single":
        for linear in (False, True):
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.75, 0.25])
            for i, (label, estimate) in enumerate(first.estimates.items()):
                color = palette[i % len(palette)]
                if estimate.spectrum is not None:
                    spectrum = estimate.spectrum
                    normalized = spectrum.values / max(float(np.max(spectrum.values)), 1e-12)
                    y = normalized if linear else 10 * np.log10(np.maximum(normalized, 1e-12))
                    fig.add_trace(
                        go.Scatter(
                            x=spectrum.grid,
                            y=y,
                            mode="lines",
                            name=label,
                            legendgroup=label,
                            line={"color": color},
                        ),
                        row=1,
                        col=1,
                    )
                fig.add_trace(
                    go.Scatter(
                        x=estimate.angles,
                        y=[i] * len(estimate.angles),
                        mode="markers",
                        name=label
                        + ("（无空间谱，只标估计角度）" if estimate.spectrum is None else " 估计"),
                        legendgroup=label,
                        marker={"color": color, "symbol": "x", "size": 10},
                    ),
                    row=2,
                    col=1,
                )
            for angle in truth(first):
                fig.add_vline(
                    x=float(angle),
                    line_dash="dash",
                    line_color="black",
                    annotation_text=f"{angle:g}°",
                    row=1,
                    col=1,
                )
            fig.update_yaxes(title_text="归一化谱" if linear else "归一化谱 (dB)", row=1, col=1)
            fig.update_yaxes(
                tickvals=list(range(len(first.estimates))),
                ticktext=list(first.estimates),
                row=2,
                col=1,
            )
            fig.update_xaxes(title_text="角度 (°)", row=2, col=1)
            fig.update_layout(title="空间谱与估计角度")
            figures["空间谱（线性）" if linear else "空间谱"] = fig
    elif result.config.get("type") == "monte_carlo":
        count = max((len(truth(t)) for t in result.points[0].trials), default=1)
        random_angles = result.config["scenario"]["sources"]["angles"]["mode"] == "random"
        fig = make_subplots(
            rows=1, cols=count, subplot_titles=[f"信源 {i + 1}" for i in range(count)]
        )
        for i, label in enumerate(labels):
            groups: dict[int, list[float]] = {}
            for trial in result.points[0].trials:
                trial_estimate = trial.estimates.get(label)
                if trial_estimate is None or len(trial_estimate.angles) != len(truth(trial)):
                    continue
                pairs, _ = kit.hungarian_matching(trial_estimate.angles, truth(trial))
                for ei, si in pairs:
                    value = (
                        trial_estimate.angles[ei] - truth(trial)[si]
                        if random_angles
                        else trial_estimate.angles[ei]
                    )
                    groups.setdefault(int(si), []).append(float(value))
            for si, samples in groups.items():
                counts, edges = np.histogram(samples, bins=min(30, max(1, len(samples))))
                fig.add_trace(
                    go.Scatter(
                        x=edges,
                        y=[*counts, 0],
                        mode="lines",
                        name=label,
                        legendgroup=label,
                        showlegend=si == 0,
                        line={"shape": "hv", "color": palette[i % len(palette)]},
                    ),
                    row=1,
                    col=si + 1,
                )
        for si in range(count):
            reference = (
                0 if random_angles else float(truth(first)[si]) if si < len(truth(first)) else None
            )
            if reference is not None:
                fig.add_vline(x=reference, line_dash="dash", line_color="black", row=1, col=si + 1)
            fig.update_xaxes(
                title_text="估计误差 (°)" if random_angles else "估计角度 (°)", row=1, col=si + 1
            )
        fig.update_layout(title="估计值分布（仅包含检出全部信源的试验）")
        figures["估计分布"] = fig
    selected = result.config.get("metrics", {}).get(
        "include", ["rmse", "success_rate", "resolution", "time"]
    )
    from ..plugins import resolve_plugin

    for metric_id in selected:
        if metric_id == "crb":
            continue
        name = "resolution_prob" if metric_id == "resolution" else metric_id
        cls = resolve_plugin(
            "metric", name, result.config.get("metrics", {}).get("origins", {}).get(name)
        )
        title = "运行时间" if name == "time" else cls.name
        unit = f"{cls.name} ({cls.unit})" if cls.unit else cls.name
        fig = go.Figure()
        for i, label in enumerate(labels):
            values = []
            markers = []
            for point in result.points:
                metrics = point_metrics(result, point, label)
                used = metrics["metric_values"].get("rmse", {}).get("n_used")
                markers.append(
                    "circle-open"
                    if used is not None and used < 0.8 * len(point.trials)
                    else "circle"
                )
                value = cast(float | None, metrics["metric_values"][name]["value"])
                values.append(value * 100 if value is not None and cls.unit == "%" else value)
            fig.add_trace(
                go.Scatter(
                    x=[
                        p.sweep_value if p.sweep_value is not None else p.point_idx
                        for p in result.points
                    ],
                    y=values,
                    name=label,
                    mode="lines+markers",
                    line={"color": palette[i % len(palette)]},
                    marker={"symbol": markers, "size": 8},
                )
            )
        if metric_id == "rmse" and "crb" in selected:
            from ..config import ExperimentConfig
            from ..crb import compute_stochastic_crb
            from ..runner.core import build_scene, expand_point

            config = ExperimentConfig.model_validate(result.config)
            bounds = []
            for point in result.points:
                point_config = expand_point(config, point.sweep_value)
                trial_bounds = []
                dynamic = (
                    point_config.scenario.sources.angles.mode == "random"
                    or point_config.scenario.sources.correlation.mode == "coherent"
                )
                for trial in point.trials if dynamic else point.trials[:1]:
                    random_index = (
                        trial.trial_idx
                        if config.options.common_random_numbers
                        else point.point_idx * config.trials + trial.trial_idx
                    )
                    scene, array = build_scene(point_config, random_index)
                    trial_bounds.extend(
                        compute_stochastic_crb(
                            array,
                            scene.config.angles,
                            np.asarray(scene.config.snr_db),
                            scene.config.N,
                            signal_covariance=scene.config.correlation.to_matrix(),
                        ).tolist()
                    )
                bounds.append(float(np.sqrt(np.mean(trial_bounds))) if trial_bounds else None)
            fig.add_trace(
                go.Scatter(
                    x=[
                        p.sweep_value if p.sweep_value is not None else p.point_idx
                        for p in result.points
                    ],
                    y=bounds,
                    name="CRB（标称阵列）",
                    line={"color": "black", "dash": "dash"},
                )
            )
        sweep = result.config.get("sweep") or {}
        axis_label = sweep.get("label") or sweep.get("path") or "实验点"
        fig.update_layout(
            title=title,
            meta={"metric": name},
            xaxis_title=f"{axis_label} {sweep.get('unit') or ''}",
            yaxis_title=unit,
        )
        figures[title] = fig
    for fig in figures.values():
        fig.update_layout(template="plotly_white", hovermode="x unified")
    return figures
