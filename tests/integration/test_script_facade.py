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


def test_sqlite_index_rebuild_and_live_script_discovery(tmp_path):
    """索引可以删除重建；服务启动后新增脚本结果也可发现。"""
    import sqlite3
    from contextlib import closing

    from arena.server.tasks import TaskManager

    manager = TaskManager(tmp_path)
    result = arena.run({"trials": 1, "algorithms": [{"id": "music"}]}, workspace=tmp_path)
    identifier = result.metadata["experiment_id"]
    assert identifier in {item["task_id"] for item in manager.list_tasks()}
    index = tmp_path / ".arena_index.sqlite"
    with closing(sqlite3.connect(index)) as connection, connection:
        assert connection.execute("SELECT count(*) FROM experiments").fetchone()[0] == 1
    index.unlink()
    rebuilt = TaskManager(tmp_path)
    assert rebuilt.get_task_status(identifier)["status"] == "completed"


def test_restart_cancels_queue_and_detects_interrupted(tmp_path):
    """仅在心跳过期且进程消失时判定中断。"""
    import time

    from arena.core.config import ExperimentConfig
    from arena.core.storage import ResultWriter
    from arena.server.tasks import TaskManager

    manager = TaskManager(tmp_path)
    queued = manager.create_task(ExperimentConfig.model_validate({}))
    running = manager.create_task(ExperimentConfig.model_validate({}))
    writer = ResultWriter(manager.tasks[running].result_path)
    writer._write_json(
        writer.output_dir / "status.json",
        {
            "status": "running",
            "pid": 99999999,
            "heartbeat": time.time() - 60,
        },
    )
    restored = TaskManager(tmp_path)
    assert restored.get_task_status(queued)["status"] == "cancelled"
    assert restored.get_task_status(running)["status"] == "interrupted"


def test_task_queue_runs_one_at_a_time(tmp_path, monkeypatch):
    """三个并发提交按 FIFO 执行，排队取消的任务不启动。"""
    import asyncio

    from arena.core.config import ExperimentConfig
    from arena.server.tasks import TaskManager

    manager = TaskManager(tmp_path)
    identifiers = [manager.create_task(ExperimentConfig.model_validate({})) for _ in range(3)]
    events = []

    async def execute(identifier):
        events.append(("start", identifier))
        await asyncio.sleep(0.01)
        events.append(("end", identifier))

    monkeypatch.setattr(manager, "_execute_task", execute)
    manager.cancel_task(identifiers[1])

    async def run():
        await asyncio.gather(*(manager.run_task(identifier) for identifier in identifiers))

    asyncio.run(run())
    assert events == [
        ("start", identifiers[0]),
        ("end", identifiers[0]),
        ("start", identifiers[2]),
        ("end", identifiers[2]),
    ]
