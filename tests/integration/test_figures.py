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
    assert len(fig.data) == 2  # 两个算法


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
def test_export_png(sweep_result):
    """测试导出 PNG。"""
    from arena.core.figures import create_rmse_curve, export_figure

    fig = create_rmse_curve(sweep_result)

    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "rmse.png"
        export_figure(fig, output_path, format="png")

        assert output_path.exists()


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
            assert "sweep_value" in header
            assert "MUSIC_rmse" in header
            assert "ESPRIT_rmse" in header


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

        data = loadmat(str(output_path))
        assert "sweep_values" in data
        assert "MUSIC_rmse" in data


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
            assert r"\begin{table}" in content
            assert "MUSIC" in content
            assert "ESPRIT" in content
            assert "RMSE" in content


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
            assert "plotly" in content.lower()  # Plotly JS

