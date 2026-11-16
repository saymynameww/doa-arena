"""Schema、扫描与指标设置的端到端回归。"""

import json

import numpy as np
import pytest

from arena.core.config import ExperimentConfig
from arena.core.runner.core import build_scene, expand_point, run_experiment
from arena.core.storage import ResultWriter
from arena.server.routes.schema import experiment_schema


def test_schema_contains_all_plugin_fields():
    """参数清单必须来自插件模型，不允许漏掉高级字段。"""
    import asyncio

    schema = asyncio.run(experiment_schema())
    assert "d" in schema["x-arrays"][0]["schema"]["properties"]
    assert len(schema["x-impairments"]) == 4
    assert "grid_start" in schema["x-algorithms"][0]["schema"]["properties"]
    assert schema["x-default"]["metrics"]["params"]["success_rate"]["threshold_deg"] == 1


def test_sweep_changes_scene_and_preserves_source():
    """扫描必须实际改变每个场景，同时不得修改原配置。"""
    config = ExperimentConfig(
        algorithms=[{"id": "music"}],
        type="sweep",
        trials=2,
        sweep={"path": "scenario.snapshots", "values": [20, 60]},
    )
    first = expand_point(config, 20)
    second = expand_point(config, 60)
    assert build_scene(first)[0].config.N == 20
    assert build_scene(second)[0].config.N == 60
    assert config.scenario.snapshots == 100
    result = run_experiment(config)
    assert len(result.points) == 2
    assert result.metadata["generator_version"] == 2


def test_random_angles_and_impairment_parameters():
    """随机场景与误差参数真实传入核心，种子相同则真值相同。"""
    config = ExperimentConfig(
        algorithms=[{"id": "music"}],
        scenario={
            "sources": {
                "K": {"values": [2, 3]},
                "angles": {"mode": "random", "range_deg": [-30, 30], "min_separation": 3},
            },
            "impairments": [{"type": "gain_phase", "params": {"sigma_g": 0.3}}],
        },
    )
    first, _ = build_scene(config, 2)
    second, _ = build_scene(config, 2)
    np.testing.assert_array_equal(first.config.angles, second.config.angles)
    assert np.all(np.diff(first.config.angles) >= 3)
    assert first.impairments[0].params.sigma_g == 0.3


def test_threshold_changes_success(tmp_path):
    """门限改变成功率，原始估计保持不变。"""
    from arena.core.metrics.compute import compute_metrics
    from arena_api import Estimate

    estimates = [Estimate(angles=np.array([-9.5, 10.5]))]
    truth = np.array([-10.0, 10.0])
    assert compute_metrics(estimates, truth, threshold_deg=1)["success_rate"] == 1
    assert compute_metrics(estimates, truth, threshold_deg=0.1)["success_rate"] == 0
    config = ExperimentConfig(algorithms=[{"id": "music"}], trials=2)
    result = run_experiment(config)
    ResultWriter(tmp_path / "中文实验").write_experiment(result)
    summary = json.loads((tmp_path / "中文实验" / "summary.json").read_text(encoding="utf-8"))
    assert "resolution_probability" in summary["points"][0]["algorithms"]["music"]
    assert "crb_deg" in summary["points"][0]


def test_invalid_scan_rejected():
    """非数值扫描和非法信源数必须被拒绝。"""
    config = ExperimentConfig(
        algorithms=[{"id": "music"}], sweep={"path": "scenario.array.type", "values": [1, 2]}
    )
    with pytest.raises(ValueError, match="数值"):
        expand_point(config, 1)
    config.scenario.sources.K = 100
    with pytest.raises(ValueError, match="信源数"):
        build_scene(config)


def test_rng_paths_do_not_depend_on_call_order():
    """同一派生路径不受其他调用影响，误差与算法使用稳定标识。"""
    from arena.core.rng import RNGTree

    tree = RNGTree(123)
    first = tree.for_trial(3).for_noise().normal(size=10)
    tree.for_trial(10).for_sources().normal(size=4)
    np.testing.assert_array_equal(first, tree.for_trial(3).for_noise().normal(size=10))
    np.testing.assert_array_equal(
        tree.for_algorithm("music", 3).normal(size=10),
        RNGTree(123).for_algorithm("music", 3).normal(size=10),
    )


def test_algorithm_parameter_sweep_and_truth_storage(tmp_path):
    """算法参数扫描与逐次真值可追溯到持久化结果。"""
    config = ExperimentConfig(
        algorithms=[{"id": "music", "params": {"grid_step": 1.0}}],
        type="sweep",
        trials=2,
        sweep={"path": "algorithms[0].params.grid_step", "values": [1, 2]},
    )
    assert expand_point(config, 2).algorithms[0].params["grid_step"] == 2
    result = run_experiment(config)
    ResultWriter(tmp_path).write_experiment(result)
    with np.load(tmp_path / "results.npz", allow_pickle=False) as data:
        np.testing.assert_array_equal(data["truth_angles"][1, 1], [-10, 10])


@pytest.mark.parametrize(
    "impairment", ["gain_phase", "position", "mutual_coupling", "element_failure"]
)
def test_each_exposed_impairment_generates_observation(impairment):
    """页面暴露的每类误差都能真正生成观测，不能只通过 Schema 校验。"""
    from arena.core.rng import RNGTree

    config = ExperimentConfig(
        algorithms=[{"id": "music"}],
        scenario={"impairments": [{"type": impairment, "realization": "per_trial", "params": {}}]},
    )
    scene, _ = build_scene(config)
    observation = scene.generate(RNGTree(42).for_trial(0))
    assert observation.X.shape == (16, 100)
    assert np.all(np.isfinite(observation.X))
