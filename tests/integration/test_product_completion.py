"""P0/P1 产品缺口的回归验收。"""

import pytest
from fastapi.testclient import TestClient

from arena.core.config import ExperimentConfig
from arena.core.runner.core import run_experiment


def test_packaged_frontend_and_spa_routes(tmp_path, monkeypatch):
    from arena.server import app

    static = tmp_path / "static"
    static.mkdir()
    (static / "index.html").write_text("<h1>Arena</h1>", encoding="utf-8")
    monkeypatch.setattr(app, "STATIC_DIR", static, raising=False)
    client = TestClient(app.create_app())
    assert client.get("/").text == "<h1>Arena</h1>"
    assert client.get("/experiments/new").status_code == 200
    assert client.get("/api/missing").status_code == 404
    assert client.get("/assets/missing.js").status_code == 404


def test_document_defaults_and_optional_display_carrier():
    from arena.core.config.scenario import AnglesConfig
    from arena.core.exploration import preview_scenario

    config = ExperimentConfig.model_validate({"scenario": {"carrier_hz": None}})
    assert config.scenario.snapshots == 200
    assert config.trials == 500
    assert config.to_document()["scenario"]["carrier_hz"] is None
    assert preview_scenario(config.scenario)["physical_spacing_cm"] is None
    assert AnglesConfig.model_validate({"mode": "separation"}).delta == 10
    single = ExperimentConfig.model_validate({"experiment": {"type": "single"}})
    assert single.trials == 1


def test_report_contains_configuration_metrics_and_print_layout():
    from arena.core.reports.html import _build_html

    result = run_experiment(ExperimentConfig(algorithms=[{"id": "music"}], trials=2))
    html = _build_html(result, "报告 <script>", {})
    from arena import __version__

    assert f"Arena v{__version__}" in html
    assert "指标汇总" in html and "RMSE" in html
    assert "配置摘要" in html and "snapshots" in html
    assert "@media print" in html and "@page" in html
    assert "报告 &lt;script&gt;" in html


def test_saved_runtime_traceback_reaches_details(tmp_path):
    from arena.core.operations import execute
    from arena.core.storage.writer import ResultWriter

    result = run_experiment(ExperimentConfig(algorithms=[{"id": "music"}], trials=2))
    trial = result.points[0].trials[0]
    trial.errors["music"] = "测试失败"
    trial.error_details["music"] = {"type": "ValueError", "traceback": "Traceback\n测试失败"}
    folder = tmp_path / "中文实验"
    ResultWriter(folder).write_experiment(result)
    details = execute("details", {"directory": str(folder)})
    error = details["error_groups"][0]["errors"][0]
    assert error["traceback"] == "Traceback\n测试失败"
    assert error["first_at"] == {"point": 0, "trial": 0}


def test_chart_identity_overrides_and_reference_lines():
    import plotly.graph_objects as go

    from arena.core.figures.identity import algorithm_style, apply_styles

    figure = go.Figure(
        [
            go.Scatter(name="算法", x=[0, 1], y=[1, 2], marker_symbol=["circle-open", "circle"]),
            go.Scatter(name="CRB", x=[0, 1], y=[1, 1], line={"color": "black", "dash": "dash"}),
        ]
    )
    apply_styles(
        figure,
        ["算法"],
        {
            "font_size": 20,
            "algorithms": {"算法": {"color": "#123456", "dash": "dot", "symbol": "square"}},
        },
    )
    assert figure.data[0].marker.symbol == ("square-open", "square")
    assert figure.data[0].line.color == "#123456"
    assert figure.layout.font.size == 20
    assert figure.data[1].line.color == "black"
    assert algorithm_style(1)["symbol"] != algorithm_style(0)["symbol"]
    with pytest.raises(ValueError):
        apply_styles(figure, ["算法"], {"font_size": 100})
    with pytest.raises(ValueError):
        apply_styles(figure, ["算法"], {"algorithms": []})


def test_failed_algorithm_keeps_configured_visual_order():
    from arena.core.metrics.summary import algorithm_labels

    result = run_experiment(
        ExperimentConfig(algorithms=[{"id": "music"}, {"id": "esprit"}], trials=1)
    )
    trial = result.points[0].trials[0]
    trial.estimates.pop("music")
    trial.errors["music"] = "首个算法失败"
    assert algorithm_labels(result) == ["music", "esprit"]


def test_progress_keeps_estimated_remaining_time():
    from arena.server.contracts import TaskProgress

    progress = TaskProgress.model_validate({"eta_seconds": 12.5})
    assert progress.model_dump()["eta_seconds"] == 12.5


@pytest.mark.slow
def test_nfr20_reference_workload(record_property):
    """规定规模的墙钟时间验收；不改变网格、试验数或算法定义。"""
    import time

    config = ExperimentConfig.model_validate(
        {
            "trials": 1000,
            "scenario": {
                "array": {"params": {"M": 16, "d": 0.5}},
                "snapshots": 200,
                "sources": {"K": 2, "angles": {"values": [-10, 10]}},
            },
            "algorithms": [
                {"id": name, "params": {"grid_step": 0.1}} for name in ("cbf", "mvdr", "music")
            ]
            + [{"id": "root_music"}, {"id": "esprit"}],
        }
    )
    start = time.perf_counter()
    result = run_experiment(config)
    elapsed = time.perf_counter() - start
    record_property("nfr20_seconds", elapsed)
    assert sum(len(p.trials) for p in result.points) == 1000
    assert all(not t.errors for p in result.points for t in p.trials)
    assert elapsed < 60, f"NFR-20 目标 60 秒，实测 {elapsed:.3f} 秒"


@pytest.mark.parametrize("stat", ["mean", "median"])
@pytest.mark.parametrize("save_estimates", [True, False])
def test_result_table_and_report_show_both_time_statistics(tmp_path, stat, save_estimates):
    """偏斜耗时使均值/中位数不同；重读存档仍展示两者，曲线口径不变。"""
    import numpy as np

    from arena.core.figures.details import result_details
    from arena.core.reports.html import _build_html
    from arena.core.storage import ResultWriter
    from arena.core.storage.reader import read_result

    config = ExperimentConfig.model_validate(
        {
            "algorithms": [{"id": "music"}],
            "trials": 3,
            "metrics": {"include": ["time"], "params": {"time": {"stat": stat}}},
            "options": {"save_estimates": save_estimates},
        }
    )
    result = run_experiment(config)
    for trial, duration in zip(result.points[0].trials, [1.0, 2.0, 9.0]):
        trial.times_ms["music"] = duration
    ResultWriter(tmp_path).write_experiment(result)
    restored = read_result(tmp_path)
    details = result_details(restored)
    columns = {column["key"]: column for column in details["columns"]}
    assert columns["time_mean"]["label"] == "平均耗时"
    assert columns["time_median"]["label"] == "中位耗时"
    # 精确可表示的人工耗时，允许浮点序列化舍入。
    np.testing.assert_allclose(
        [details["rows"][0]["metrics"]["time_mean"], details["rows"][0]["metrics"]["time_median"]],
        [4.0, 2.0],
        atol=1e-12,
    )
    html = _build_html(restored, "耗时验收", {})
    assert "平均耗时" in html and "中位耗时" in html
