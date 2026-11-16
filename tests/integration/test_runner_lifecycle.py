"""运行器资源释放、取消和错误隔离的回归测试。"""

import numpy as np
import pytest

from arena.core.config import AlgorithmConfig, ExperimentConfig, SweepConfig
from arena.core.runner import core
from arena.core.storage import ResultWriter
from arena.core.storage.reader import read_result
from arena_api import Algorithm, Estimate


@pytest.fixture
def lifecycle_plugin(monkeypatch):
    """登记带资源事件记录的算法，避免依赖真实模型。"""
    events = []

    class Probe(Algorithm):
        id = "probe"
        name = "资源探针"
        version = "1.0.0"

        def load(self, params, ctx):
            events.append("load")

        def configure(self, params, array, ctx):
            events.append("configure")

        def estimate(self, obs, ctx):
            events.append("estimate")
            return Estimate(np.array([-10.0, 10.0]))

        def close(self):
            events.append("close")

    monkeypatch.setattr("arena.core.plugins.resolve_algorithm", lambda *args: Probe)
    return events


def config():
    """构造两个扫描点，便于验证跨点资源复用。"""
    return ExperimentConfig(
        type="sweep",
        trials=3,
        sweep=SweepConfig(path="scenario.sources.snr_db", values=[0, 10]),
        algorithms=[AlgorithmConfig(id="probe")],
        options={"warmup": False},
    )


def test_resource_reuse(lifecycle_plugin):
    core.run_experiment(config())
    assert lifecycle_plugin == [
        "load",
        "configure",
        *["estimate"] * 3,
        "configure",
        *["estimate"] * 3,
        "close",
    ]


def test_close_on_callback_error(lifecycle_plugin):
    def broken_callback(*args):
        raise RuntimeError("回调异常")

    with pytest.raises(RuntimeError, match="回调异常"):
        core.run_experiment(config(), broken_callback)
    assert lifecycle_plugin[-1] == "close"


def test_cancel_partial_roundtrip(lifecycle_plugin, tmp_path):
    completed = []
    result = core.run_experiment(
        config(),
        lambda count, *args: completed.append(count),
        cancel_callback=lambda: len(completed) == 4,
    )
    assert result.metadata["status"] == "cancelled"
    assert [len(p.trials) for p in result.points] == [3, 1]
    assert lifecycle_plugin[-1] == "close"
    directory = tmp_path / "中文目录" / "experiment"
    ResultWriter(directory).write_experiment(result)
    recovered = read_result(directory)
    assert [len(p.trials) for p in recovered.points] == [3, 1]
    np.testing.assert_array_equal(
        recovered.points[1].trials[0].estimates["probe"].angles,
        result.points[1].trials[0].estimates["probe"].angles,
    )


def test_consecutive_errors_reset_per_point(lifecycle_plugin, monkeypatch):
    from arena.core.plugins import resolve_algorithm

    cls = resolve_algorithm("probe")

    def bad_estimate(self, obs, ctx):
        lifecycle_plugin.append("bad_estimate")
        raise ValueError("故障探针")

    monkeypatch.setattr(cls, "estimate", bad_estimate)
    experiment = config()
    experiment.options.max_consecutive_errors = 1
    result = core.run_experiment(experiment)
    assert lifecycle_plugin.count("bad_estimate") == 2
    assert all("probe" in t.errors for p in result.points for t in p.trials)
    assert lifecycle_plugin[-1] == "close"


def test_atomic_write_retries_transient_reader_lock(tmp_path, monkeypatch):
    """Windows 上读取状态文件时的瞬时占用不能使计算失败。"""
    from pathlib import Path

    original = Path.replace
    attempts = []

    def replace(source, target):
        attempts.append(target)
        if len(attempts) < 3:
            raise PermissionError("模拟读端短暂占用")
        return original(source, target)

    monkeypatch.setattr(Path, "replace", replace)
    writer = ResultWriter(tmp_path)
    writer._write_json(tmp_path / "status.json", {"completed_trials": 1})
    assert len(attempts) == 3
    assert not list(tmp_path.glob("*.tmp"))
