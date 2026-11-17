"""结果文件必须满足开放格式，而不只能够被本项目读回。"""

import json

import numpy as np

import arena


def test_standard_result_arrays_and_metadata(tmp_path):
    """独立按键名和维度读取标准数组，验证版本记录。"""
    result = arena.run(
        {
            "type": "single",
            "trials": 1,
            "algorithms": [{"id": "music"}, {"id": "esprit"}],
        },
        workspace=tmp_path,
    )
    directory = tmp_path / "experiments" / result.metadata["experiment_id"]
    with np.load(directory / "results.npz", allow_pickle=False) as raw:
        assert raw["truth"].shape == (1, 1, 2)
        assert raw["estimates"].shape == (1, 2, 1, 2)
        assert raw["matched"].shape == (1, 2, 1, 2)
        assert raw["status"].dtype == np.uint8
        np.testing.assert_array_equal(raw["status"], np.zeros((1, 2, 1)))
        assert raw["metric__rmse__value"].shape == (1, 2)
        assert raw["spectrum__0__values"].shape[:2] == (1, 1)
        assert raw["observation__X"].shape == (1, 1, 16, 200)
    summary = json.loads((directory / "summary.json").read_text(encoding="utf-8"))
    assert summary["schema_version"] == 1 and summary["complete"]
    assert [a["id"] for a in summary["algorithms"]] == ["music", "esprit"]
    assert len(summary["metrics"]["rmse"]["value"][0]) == 2
    metadata = json.loads((directory / "meta.json").read_text(encoding="utf-8"))
    assert metadata["versions"]["generator_version"] == 3
    assert metadata["plugins"]["algorithm/music"]["version"]
    assert metadata["config_hash"].startswith("sha256:")
    assert "hostname" not in metadata["environment"]
    assert (directory / "notes.json").exists()


def test_not_run_does_not_count_as_metric_failure():
    """加载失败的状态 7 不参与成功率分母。"""
    from arena.core.metrics.summary import point_metrics
    from arena.core.runner.results import ExperimentResult, SweepPointResult, TrialResult

    point = SweepPointResult(
        0,
        None,
        [
            TrialResult(0, {}, {"bad": "load/configure 失败：参数错误"}, {}, np.array([-10, 10])),
        ],
    )
    metrics = point_metrics(ExperimentResult({}, [point], {}), point, "bad")
    assert metrics["num_trials"] == 0
    assert np.isnan(metrics["success_rate"])
