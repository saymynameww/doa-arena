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
    assert float(row["测试算法_rmse"]) == pytest.approx(1)
    assert float(row["测试算法_success_rate"]) == 0


def test_mat_supports_chinese_algorithm_labels(result, tmp_path):
    path = tmp_path / "实验.mat"
    export_to_mat(result, path)
    data = loadmat(path)
    assert data["algorithm_0_rmse"].item() == pytest.approx(1)
    assert data["algorithm_0_success_rate"].item() == 0
    assert "测试算法" in str(data["metadata"])


def test_latex_single_point_real_truth(result, tmp_path):
    path = tmp_path / "实验.tex"
    export_to_latex(result, path)
    content = path.read_text(encoding="utf-8")
    assert "测试算法" in content
    assert "1.000" in content
    assert "0.0\\%" in content
