"""导出必须使用逐次真值、全部失败试验与用户成功门限。"""

import csv

import numpy as np
import pytest
from scipy.io import loadmat

from arena.core.export.csv import export_to_csv
from arena.core.export.latex import export_to_latex
from arena.core.export.matlab import export_to_mat
from arena.core.runner.results import ExperimentResult, SweepPointResult, TrialResult
from arena_api import Estimate


@pytest.fixture
def result():
    return ExperimentResult(
        {
            "name": "随机角度",
            "trials": 2,
            "metrics": {"params": {"success_rate": {"threshold_deg": 0.1}}},
        },
        [
            SweepPointResult(
                0,
                None,
                [
                    TrialResult(0, {}, {"测试算法": "故障"}, {}, np.array([20.0])),
                    TrialResult(
                        1,
                        {"测试算法": Estimate.from_angles([31.0])},
                        {},
                        {"测试算法": 2.0},
                        np.array([30.0]),
                    ),
                ],
            )
        ],
        {},
    )


def test_csv_uses_real_truth_and_failure(result, tmp_path):
    path = tmp_path / "实验.csv"
    export_to_csv(result, path)
    with path.open(encoding="utf-8-sig", newline="") as stream:
        row = next(csv.DictReader(stream))
    assert float(row["测试算法"]) == pytest.approx(1)
    export_to_csv(result, path, metric="success_rate")
    with path.open(encoding="utf-8-sig", newline="") as stream:
        assert float(next(csv.DictReader(stream))["测试算法"]) == 0


def test_mat_supports_chinese_algorithm_labels(result, tmp_path):
    path = tmp_path / "实验.mat"
    export_to_mat(result, path)
    data = loadmat(path, simplify_cells=True, uint16_codec="utf-16-le")["arena"]
    assert data["metric"]["rmse"] == pytest.approx(1)
    assert data["metric"]["success_rate"] == 0
    assert "测试算法" in str(data["algorithms"])


def test_latex_single_point_real_truth(result, tmp_path):
    path = tmp_path / "实验.tex"
    export_to_latex(result, path)
    content = path.read_text(encoding="utf-8")
    assert "测试算法" in content
    assert "1.000" in content
    assert r"\toprule" in content
    assert r"\begin{table}" not in content


@pytest.mark.matlab
@pytest.mark.slow
def test_matlab_loads_chinese_and_nan(result, tmp_path):
    """实际 MATLAB 检查 miUTF16、cell 和 NaN，缺少 MATLAB 时跳过。"""
    import shutil
    import subprocess
    import sys
    from pathlib import Path

    matlab = shutil.which("matlab")
    if matlab is None:
        pytest.skip("未安装 MATLAB")
    path = tmp_path / "chinese.mat"
    export_to_mat(result, path)
    fixture = Path(__file__).resolve().parents[1] / "fixtures/chinese_utf16.mat"
    expression = (
        "s=load('" + path.as_posix().replace("'", "''") + "');"
        "assert(isequal(fieldnames(s),{'arena'}));"
        "assert(isequal(double(s.arena.name),[38543 26426 35282 24230]));"
        "assert(iscell(s.arena.algorithms));"
        "assert(isequal(double(s.arena.algorithms{1}),[27979 35797 31639 27861]));"
        "assert(s.arena.metric.rmse==1);"
        "assert(any(isnan(s.arena.estimates(:))));"
        "f=load('" + fixture.as_posix().replace("'", "''") + "');"
        "assert(isnan(f.arena.metric.rmse(2)));"
    )
    # 使用公开启动入口，让启动器完成环境初始化并返回批处理退出码。
    # MathWorks matlab (Windows)：脚本调用需要 -wait。
    arguments = [matlab, *(["-wait"] if sys.platform == "win32" else [])]
    sentinel = tmp_path / "matlab-passed.txt"
    expression += (
        "fid=fopen('"
        + sentinel.as_posix().replace("'", "''")
        + "','w');fprintf(fid,'passed');fclose(fid);"
    )
    log = tmp_path / "matlab.log"
    with log.open("w", encoding="utf-8") as stream:
        process = subprocess.Popen([*arguments, "-batch", expression], stdout=stream, stderr=stream)
        try:
            code = process.wait(timeout=180)
        except subprocess.TimeoutExpired:
            import psutil

            # 启动器退出前同时回收本次测试派生的 MATLAB，避免残留进程。
            for child in psutil.Process(process.pid).children(recursive=True):
                try:
                    child.kill()
                except psutil.NoSuchProcess:
                    pass
            process.kill()
            process.wait()
            pytest.fail(
                "MATLAB 批处理超过 180 秒：" + log.read_text(encoding="utf-8", errors="replace")
            )
    assert code == 0, log.read_text(encoding="utf-8", errors="replace")
    assert sentinel.read_text(encoding="utf-8") == "passed"
