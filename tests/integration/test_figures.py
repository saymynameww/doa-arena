"""测试图表生成和导出。"""

import tempfile
from pathlib import Path

import pytest

from arena import AlgorithmConfig, ExperimentConfig, ExperimentType, run_experiment
from arena.core.config import SweepConfig


def _has_kaleido() -> bool:
    """检查是否安装了 kaleido。"""
    try:
        import kaleido  # noqa: F401

        return True
    except ImportError:
        return False


def _has_scipy() -> bool:
    """检查是否安装了 scipy。"""
    try:
        import scipy  # noqa: F401

        return True
    except ImportError:
        return False


@pytest.fixture
def sweep_result():
    """扫描实验结果。"""
    config = ExperimentConfig(
        name="Test Sweep",
        type=ExperimentType.SWEEP,
        trials=10,
        algorithms=[
            AlgorithmConfig(id="music", label="MUSIC"),
            AlgorithmConfig(id="esprit", label="ESPRIT"),
        ],
        sweep=SweepConfig(
            path="scenario.sources.snr_db",
            values=[0, 5, 10],
            label="SNR",
            unit="dB",
        ),
    )

    return run_experiment(config)


def test_create_rmse_curve(sweep_result):
    """测试创建 RMSE 曲线。"""
    from arena.core.figures import create_rmse_curve

    fig = create_rmse_curve(sweep_result)

    # 验证图表创建成功
    assert fig is not None
    assert len(fig.data) == 3  # 两个算法与标称阵列 CRB


def test_create_success_rate_curve(sweep_result):
    """测试创建成功率曲线。"""
    from arena.core.figures import create_success_rate_curve

    fig = create_success_rate_curve(sweep_result)

    assert fig is not None
    assert len(fig.data) == 2


def test_chart_generator(sweep_result):
    """测试图表生成器。"""
    from arena.core.figures import ChartGenerator

    gen = ChartGenerator(sweep_result)
    charts = gen.create_all_charts()

    # 应该包含多个图表
    assert "rmse_curve" in charts
    assert "success_rate_curve" in charts
    assert "time_curve" in charts


def test_export_html(sweep_result):
    """测试导出 HTML。"""
    from arena.core.figures import create_rmse_curve, export_figure

    fig = create_rmse_curve(sweep_result)

    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "rmse.html"
        export_figure(fig, output_path, format="html")

        # 验证文件存在
        assert output_path.exists()
        assert output_path.stat().st_size > 0


@pytest.mark.skipif(
    not _has_kaleido(),
    reason="kaleido not installed",
)
@pytest.mark.slow
def test_export_png(sweep_result):
    """测试导出 PNG。"""
    from arena.core.figures import create_rmse_curve, export_figure

    fig = create_rmse_curve(sweep_result)

    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "rmse.png"
        export_figure(fig, output_path, format="png", width=640, height=480)

        assert output_path.exists()
        import struct

        # PNG IHDR 像素尺寸：640×480 的逻辑尺寸按 300/96 倍导出。
        assert struct.unpack(">II", output_path.read_bytes()[16:24]) == (2000, 1500)


def test_export_csv(sweep_result):
    """测试导出 CSV。"""
    from arena.core.export import export_to_csv

    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "results.csv"
        export_to_csv(sweep_result, output_path)

        # 验证文件存在
        assert output_path.exists()

        # 验证内容
        with open(output_path, encoding="utf-8-sig") as f:
            lines = f.readlines()
            assert len(lines) > 1  # 表头 + 数据行

            # 检查表头
            header = lines[0].strip()
            assert "SNR (dB)" in header
            assert "MUSIC" in header
            assert "ESPRIT" in header


@pytest.mark.skipif(
    not _has_scipy(),
    reason="scipy not installed",
)
def test_export_mat(sweep_result):
    """测试导出 MAT。"""
    from arena.core.export import export_to_mat

    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "results.mat"
        export_to_mat(sweep_result, output_path)

        assert output_path.exists()

        # 验证可以读取
        from scipy.io import loadmat

        data = loadmat(str(output_path), simplify_cells=True)["arena"]
        assert "sweep" in data
        assert "rmse" in data["metric"]


def test_export_latex(sweep_result):
    """测试导出 LaTeX。"""
    from arena.core.export import export_to_latex

    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "results.tex"
        export_to_latex(sweep_result, output_path, caption="测试结果")

        assert output_path.exists()

        # 验证内容
        with open(output_path, encoding="utf-8") as f:
            content = f.read()
            assert r"\begin{tabular}" in content
            assert "MUSIC" in content
            assert "ESPRIT" in content
            assert r"\toprule" in content


def test_all_exports_together(sweep_result):
    """测试所有导出功能一起使用。"""
    from arena.core.export import export_to_csv, export_to_latex
    from arena.core.figures import ChartGenerator, export_figure

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)

        # 图表
        gen = ChartGenerator(sweep_result)
        charts = gen.create_all_charts()

        for name, fig in charts.items():
            export_figure(fig, output_dir / f"{name}.html", format="html")

        # CSV
        export_to_csv(sweep_result, output_dir / "results.csv")

        # LaTeX
        export_to_latex(sweep_result, output_dir / "results.tex")

        # 验证所有文件
        assert (output_dir / "rmse_curve.html").exists()
        assert (output_dir / "success_rate_curve.html").exists()
        assert (output_dir / "results.csv").exists()
        assert (output_dir / "results.tex").exists()


@pytest.mark.slow
def test_html_report(sweep_result):
    """测试生成 HTML 报告。"""
    from arena.core.reports import generate_html_report

    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "report.html"
        generate_html_report(sweep_result, output_path, title="测试报告")

        # 验证文件存在
        assert output_path.exists()

        # 验证内容
        with open(output_path, encoding="utf-8") as f:
            content = f.read()
            assert "测试报告" in content
            assert "MUSIC" in content
            assert "ESPRIT" in content
            assert "<svg" in content
            from arena.core.figures.presentation import build_figures

            assert content.count("<svg") == len(build_figures(sweep_result))
            assert "配置摘要" in content and "指标汇总" in content
            assert "平均耗时" in content and "中位耗时" in content
            assert "cdn.plot.ly" not in content


def test_presentation_probability_units_and_non_snr_axis(sweep_result):
    """百分比轴的数据必须是百分数，缺少标签时保留真实扫描路径。"""
    from arena.core.figures.presentation import build_figures
    from arena.core.metrics.summary import point_metrics

    sweep_result.config["sweep"]["label"] = ""
    figures = build_figures(sweep_result)
    chart = next(f for f in figures.values() if f.layout.meta["metric"] == "success_rate")
    expected = [
        point_metrics(sweep_result, p, "MUSIC")["metric_values"]["success_rate"]["value"] * 100
        for p in sweep_result.points
    ]
    import numpy as np

    np.testing.assert_allclose(chart.data[0].y, expected, atol=1e-12)
    assert "scenario.sources.snr_db" in chart.layout.xaxis.title.text


def test_result_details_match_figures(sweep_result):
    """表格与曲线的百分比单位一致，并保留有效次数和参考线比值。"""
    import numpy as np

    from arena.core.figures.details import result_details
    from arena.core.figures.presentation import build_figures

    detail = result_details(sweep_result)
    rows = [r for r in detail["rows"] if r["algorithm"] == "MUSIC"]
    chart = next(
        f for f in build_figures(sweep_result).values() if f.layout.meta["metric"] == "success_rate"
    )
    # 同一汇总的两种展示仅允许浮点表示误差。
    np.testing.assert_allclose(
        [r["metrics"]["success_rate"] for r in rows], chart.data[0].y, atol=1e-12
    )
    assert all(r["n_used"] == 10 and r["n_total"] == 10 for r in rows)
    assert rows[0]["efficiency"] > 0


def test_single_and_distribution_presentation():
    """单次谱归一化、无谱算法独立标记；分布按信源展示且跳过漏检试验。"""
    import numpy as np

    from arena.core.figures.presentation import build_figures
    from arena.core.runner.results import ExperimentResult, SweepPointResult, TrialResult
    from arena_api import Estimate, Spectrum

    config = ExperimentConfig(algorithms=[{"id": "music"}], type="single").model_dump(mode="json")
    trial = TrialResult(
        0,
        {
            "谱算法": Estimate(
                np.array([-10.0, 10.0]),
                Spectrum(np.array([-10.0, 0.0, 10.0]), np.array([2.0, 1.0, 4.0]), "power"),
            ),
            "无谱算法": Estimate.from_angles([-9.0, 11.0]),
        },
        {},
        {"谱算法": 1.0, "无谱算法": 1.0},
        truth_angles=np.array([-10.0, 10.0]),
    )
    result = ExperimentResult(config, [SweepPointResult(0, None, [trial])], {})
    figures = build_figures(result)
    assert np.max(figures["空间谱"].data[0].y) == 0
    assert np.max(figures["空间谱（线性）"].data[0].y) == 1
    assert "无空间谱" in figures["空间谱"].data[-1].name
    config["type"] = "monte_carlo"
    result.points[0].trials.append(
        TrialResult(
            1,
            {"谱算法": Estimate.from_angles([-10.0])},
            {},
            {},
            truth_angles=np.array([-10.0, 10.0]),
        )
    )
    dist = build_figures(result)["估计分布"]
    assert len(dist.data) == 4
    assert sum(dist.data[0].y) == 1


def test_comparison_uses_metric_identity_and_rejects_mismatched_axes(sweep_result):
    """同指标导出不依赖图表顺序，禁止比较不同扫描变量。"""
    from copy import deepcopy

    from arena.core.figures.compare import comparison_figure

    other = deepcopy(sweep_result)
    other.config["metrics"]["include"] = ["time", "success_rate", "rmse"]
    fig = comparison_figure([sweep_result, other], "success_rate")
    assert len(fig.data) == 4
    assert "%" in fig.layout.yaxis.title.text
    assert fig.data[0].line.color == fig.data[2].line.color
    assert fig.data[0].line.dash != fig.data[2].line.dash
    other.config["sweep"]["path"] = "scenario.snapshots"
    with pytest.raises(ValueError, match="扫描变量不同"):
        comparison_figure([sweep_result, other], "rmse")


def test_result_reader_releases_archive_before_decoding(sweep_result, tmp_path, monkeypatch):
    """并发图表读取不能持有磁盘句柄，也不能逐试验重复解压整块数组。"""
    import numpy as np

    from arena.core.storage import ResultWriter
    from arena.core.storage.reader import read_result

    ResultWriter(tmp_path).write_experiment(sweep_result)
    original = np.lib.npyio.NpzFile.__getitem__
    accesses = {}

    def counted(self, key):
        accesses[key] = accesses.get(key, 0) + 1
        assert accesses[key] == 1, f"数组 {key} 被重复解压"
        # Windows 下读取句柄若仍占用原文件，此处原子替换会失败。
        target = tmp_path / "results.npz"
        replacement = tmp_path / "replacement.npz"
        replacement.write_bytes(target.read_bytes())
        replacement.replace(target)
        return original(self, key)

    monkeypatch.setattr(np.lib.npyio.NpzFile, "__getitem__", counted)
    restored = read_result(tmp_path)
    assert sum(len(point.trials) for point in restored.points) == 30
