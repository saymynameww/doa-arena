"""固定场景集、版本隔离、显式扫描点和可追溯排行。"""

import copy
import json

import pytest

from arena import benchmark
from arena.core.benchmark import create_run


def suite_document(version="1.0"):
    return {
        "schema_version": 1,
        "suite_id": "test-suite",
        "version": version,
        "name": "测试场景集",
        "scenarios": [
            {
                "name": "snr",
                "config": {
                    "seed": 42,
                    "scenario": {"array": {"params": {"M": 8, "d": 0.5}}, "snapshots": 20},
                    "experiment": {
                        "type": "sweep",
                        "trials": 2,
                        "sweep": {"path": "scenario.sources.snr_db", "values": [0, 10]},
                    },
                    "metrics": {"include": ["rmse", "success_rate"]},
                },
            },
            {
                "name": "single",
                "config": {
                    "seed": 43,
                    "experiment": {"type": "single", "trials": 1},
                    "metrics": {"include": ["rmse", "success_rate"]},
                },
            },
        ],
        "leaderboard": [
            {"scenario": "snr", "metric": "rmse", "at": 0, "label": "RMSE @ 0dB"},
            {"scenario": "single", "metric": "success_rate", "at": 0, "label": "成功率"},
        ],
    }


def test_immutable_suite_and_preflight(tmp_path):
    document = suite_document()
    first = benchmark.save_suite(document, tmp_path)
    assert benchmark.save_suite(document, tmp_path)["hash"] == first["hash"]
    changed = copy.deepcopy(document)
    changed["scenarios"][0]["config"]["seed"] = 100
    with pytest.raises(ValueError, match="版本"):
        benchmark.save_suite(changed, tmp_path)
    del changed["scenarios"][0]["config"]["seed"]
    with pytest.raises(ValueError, match="seed"):
        benchmark.BenchmarkSuite.model_validate(changed)
    with pytest.raises(ValueError):
        create_run(tmp_path, "test-suite", "1.0", [{"id": "missing"}])
    assert not list((tmp_path / "experiments").glob("*"))


def test_zero_position_error_is_valid_reference_point():
    import numpy as np

    from arena.core.impairments.position import PositionError

    params = PositionError.Params(sigma=0)
    assert params.sigma == 0
    plugin = PositionError()
    actual = plugin.describe(plugin.sample(np.random.default_rng(1), 8), params, 8)
    np.testing.assert_array_equal(actual["offset"], np.zeros((8, 3)))


def test_benchmark_run_version_isolation_and_missing_scenes(tmp_path):
    benchmark.save_suite(suite_document(), tmp_path)
    benchmark.save_suite(suite_document("2.0"), tmp_path)
    algorithms = [{"id": "music", "label": "baseline", "params": {"grid_step": 1}}]
    partial = benchmark.run_suite(tmp_path, "test-suite", "1.0", algorithms, ["snr"])
    board = benchmark.leaderboard(tmp_path, "test-suite", "1.0")
    assert board["rows"][0]["missing"] == ["single"]
    assert not benchmark.leaderboard(tmp_path, "test-suite", "2.0")["rows"]
    record = benchmark.run_suite(tmp_path, "test-suite", "1.0", algorithms)
    board = benchmark.leaderboard(tmp_path, "test-suite", "1.0")
    row = board["rows"][0]
    assert row["rank"] == 1
    assert row["missing"] == []
    assert all(cell["run_id"] == record["run_id"] for cell in row["values"])
    directory = tmp_path / "experiments" / record["experiments"]["snr"]
    summary = json.loads((directory / "summary.json").read_text(encoding="utf-8"))
    assert (
        row["values"][0]["value"]
        == summary["points"][0]["algorithms"]["baseline"]["metric_values"]["rmse"]["value"]
    )
    meta = json.loads((directory / "meta.json").read_text(encoding="utf-8"))
    assert meta["benchmark"]["run_id"] == record["run_id"]
    assert meta["mode"] == "script"
    old = benchmark.leaderboard(tmp_path, "test-suite", "1.0", revision=partial["run_id"])
    assert old["rows"][0]["missing"] == ["single"]
    assert board["columns"][1]["higher_is_better"] is True
    assert board["columns"][0]["unit"] == "°"
    assert board["columns"][1]["unit"] == "%"


def test_changed_experiment_cannot_enter_fixed_benchmark(tmp_path):
    from arena.core.storage.writer import ResultWriter

    benchmark.save_suite(suite_document(), tmp_path)
    record = benchmark.run_suite(tmp_path, "test-suite", "1.0", [{"id": "music"}], ["snr"])
    directory = tmp_path / "experiments" / record["experiments"]["snr"]
    config = json.loads((directory / "config.json").read_text(encoding="utf-8"))
    config["metrics"]["params"]["success_rate"]["threshold_deg"] = 90
    ResultWriter(directory)._write_json(directory / "config.json", config)
    board = benchmark.leaderboard(tmp_path, "test-suite", "1.0")
    assert board["rows"][0]["values"][0] is None
    assert any("偏离固定场景" in failure for failure in board["failures"])


@pytest.mark.slow
def test_all_builtin_scene_shapes(tmp_path):
    suites = benchmark.list_suites(tmp_path)
    builtin = next(s for s in suites if s["suite_id"] == "doa-basic")
    smoke = {k: v for k, v in builtin.items() if k not in {"hash", "builtin"}}
    smoke["suite_id"] = "smoke-only"
    for scene in smoke["scenarios"]:
        scene["config"]["experiment"]["trials"] = 2
    benchmark.save_suite(smoke, tmp_path)
    record = benchmark.run_suite(
        tmp_path, "smoke-only", "1.0", [{"id": "esprit", "params": {"smoothing": "fb"}}]
    )
    for identifier in record["experiments"].values():
        status = json.loads(
            (tmp_path / "experiments" / identifier / "status.json").read_text(encoding="utf-8")
        )
        assert status["status"] == "completed", status
    board = benchmark.leaderboard(tmp_path, "smoke-only", "1.0")
    assert not board["failures"]
    assert board["rows"][0]["missing"] == []
