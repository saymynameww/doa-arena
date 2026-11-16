"""脚本模式与核心执行结果一致，配置可以重新加载。"""

import numpy as np

import arena
from arena_api import Algorithm, Estimate


def test_script_run_load_and_direct_plugin(tmp_path):
    events = []

    class DebugAlgorithm(Algorithm):
        id = "debug"
        name = "调试算法"
        version = "1.0.0"

        def load(self, params, ctx):
            events.append("load")

        def estimate(self, obs, ctx):
            return Estimate.from_angles([-10, 10])

        def close(self):
            events.append("close")

    workspace = arena.Workspace(tmp_path / "中文工作目录")
    result = arena.run(
        {
            "name": "脚本运行",
            "type": "single",
            "trials": 1,
            "algorithms": [DebugAlgorithm.spec(label="debug"), arena.algorithm_spec("music")],
        },
        workspace=workspace,
    )
    recovered = arena.load_result(workspace, result.metadata["experiment_id"])
    assert events == ["load", "close"]
    for label in ("debug", "music"):
        np.testing.assert_array_equal(
            result.points[0].trials[0].estimates[label].angles,
            recovered.points[0].trials[0].estimates[label].angles,
        )


def test_spec_validates_parameters_immediately():
    import pytest

    from arena.core.algorithms import MUSIC

    with pytest.raises(ValueError):
        MUSIC.spec(grid_step=-1)


def test_web_history_recovers_script_results_without_index(tmp_path):
    from arena.server.tasks import TaskManager

    result = arena.run(
        {"name": "可发现实验", "type": "single", "trials": 1, "algorithms": [{"id": "music"}]},
        workspace=tmp_path,
    )
    manager = TaskManager(tmp_path)
    assert result.metadata["experiment_id"] in manager.tasks
    recovered = manager.tasks[result.metadata["experiment_id"]]
    assert recovered.status.value == "completed"
    assert recovered.config.name == "可发现实验"
