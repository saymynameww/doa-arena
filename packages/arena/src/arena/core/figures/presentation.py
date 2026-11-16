"""网页、脚本和导出共用的结果图表。"""

from __future__ import annotations

from typing import cast

import numpy as np
import plotly.graph_objects as go

from arena_api import Estimate, kit

from ..metrics import compute_metrics
from ..runner.results import ExperimentResult, TrialResult


def build_figures(result: ExperimentResult) -> dict[str, go.Figure]:
    """按实验类型生成真实空间谱、匹配分布及指标曲线。"""
    figures: dict[str, go.Figure] = {}
    if not result.points or not result.points[0].trials:
        return figures
    labels = list(
        dict.fromkeys(
            label for p in result.points for t in p.trials for label in [*t.estimates, *t.errors]
        )
    )
    first = result.points[0].trials[0]
    fallback = np.asarray(result.config["scenario"]["sources"]["angles"].get("values") or [])

    def truth(trial: TrialResult) -> np.ndarray:
        return trial.truth_angles if trial.truth_angles is not None else fallback

    if result.config.get("type") == "single":
        fig = go.Figure()
        for label, estimate in first.estimates.items():
            if estimate.spectrum is not None:
                spectrum = estimate.spectrum
                fig.add_trace(
                    go.Scatter(
                        x=spectrum.grid,
                        y=10 * np.log10(np.maximum(spectrum.values, 1e-12)),
                        mode="lines",
                        name=label,
                    )
                )
            fig.add_trace(
                go.Scatter(
                    x=estimate.angles,
                    y=[0] * len(estimate.angles),
                    mode="markers",
                    name=label + " 估计",
                    marker={"symbol": "x", "size": 10},
                )
            )
        for angle in truth(first):
            fig.add_vline(x=float(angle), line_dash="dash", line_color="black")
        fig.update_layout(
            title="空间谱与估计角度", xaxis_title="角度 (°)", yaxis_title="归一化谱 (dB)"
        )
        figures["空间谱"] = fig
    elif result.config.get("type") == "monte_carlo":
        fig = go.Figure()
        for label in labels:
            groups: dict[int, list[float]] = {}
            for trial in result.points[0].trials:
                if label not in trial.estimates:
                    continue
                estimate = trial.estimates[label]
                pairs, _ = kit.hungarian_matching(estimate.angles, truth(trial))
                for ei, si in pairs:
                    groups.setdefault(int(si), []).append(
                        float(estimate.angles[ei] - truth(trial)[si])
                    )
            for si, errors in groups.items():
                fig.add_trace(go.Histogram(x=errors, name=f"{label} · 信源 {si + 1}", opacity=0.6))
        fig.update_layout(
            title="按信源匹配的估计误差分布",
            xaxis_title="估计误差 (°)",
            yaxis_title="次数",
            barmode="overlay",
        )
        figures["估计分布"] = fig
    selected = result.config.get("metrics", {}).get(
        "include", ["rmse", "success_rate", "resolution", "time"]
    )
    threshold = (
        result.config.get("metrics", {})
        .get("params", {})
        .get("success_rate", {})
        .get("threshold_deg", 1)
    )
    for key, title, unit, metric_id in [
        ("rmse_mean", "RMSE", "RMSE (°)", "rmse"),
        ("success_rate", "成功率", "成功率", "success_rate"),
        ("resolution_probability", "分辨概率", "分辨概率", "resolution"),
        ("avg_time_ms", "运行时间", "毫秒", "time"),
    ]:
        if metric_id not in selected:
            continue
        fig = go.Figure()
        for label in labels:
            values = []
            for point in result.points:
                estimates = [
                    trial.estimates.get(label, Estimate.from_angles([])) for trial in point.trials
                ]
                metrics = compute_metrics(
                    estimates,
                    fallback,
                    threshold_deg=threshold,
                    truths=[truth(t) for t in point.trials],
                )
                if key == "avg_time_ms":
                    durations = [t.times_ms[label] for t in point.trials if label in t.times_ms]
                    values.append(float(np.mean(durations)) if durations else None)
                else:
                    values.append(cast(float | None, dict(metrics)[key]))
            fig.add_trace(
                go.Scatter(
                    x=[
                        p.sweep_value if p.sweep_value is not None else p.point_idx
                        for p in result.points
                    ],
                    y=values,
                    name=label,
                    mode="lines+markers",
                )
            )
        if key == "rmse_mean" and "crb" in selected:
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
                    scene, array = build_scene(point_config, trial.trial_idx)
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
        fig.update_layout(
            title=title,
            xaxis_title=f"{sweep.get('label') or '实验点'} {sweep.get('unit') or ''}",
            yaxis_title=unit,
        )
        figures[title] = fig
    for fig in figures.values():
        fig.update_layout(template="plotly_white", hovermode="closest")
    return figures
