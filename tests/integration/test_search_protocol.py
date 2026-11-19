"""固定网格公平基线、显式变体与 v1 历史语义回归。"""

import asyncio
import json

import numpy as np
import pytest
from scripts.audit_music_peaks import make_array, make_context

from arena.core.algorithms import CBF, MUSIC, MVDR, RootMUSIC
from arena.core.config import ExperimentConfig
from arena.core.rng import RNGTree
from arena.core.runner.core import build_scene, expand_point, run_experiment
from arena.core.storage import ResultWriter
from arena.core.storage.reader import read_result
from arena.server.routes.schema import experiment_schema, normalize_configuration
from arena_api import Observation, SpectrumSearchParams, kit


def test_new_defaults_share_fixed_grid_without_touching_gridless_algorithms():
    config = ExperimentConfig(
        search_grid={"scan_min": -60, "scan_max": 60, "grid_step": 0.2},
        algorithms=[{"id": name} for name in ("cbf", "mvdr", "music", "root_music", "esprit")],
        trials=2,
    )
    for entry in config.algorithms[:3]:
        assert entry.params["peak_refinement"] == "none"
        assert entry.params["grid_mode"] == "shared"
        assert entry.params["grid_step"] == 0.2
    for entry in config.algorithms[3:]:
        assert entry.params == {}
    result = run_experiment(config)
    for trial in result.points[0].trials:
        for name in ("cbf", "mvdr", "music"):
            angles = trial.estimates[name].angles
            # 固定网格允许浮点舍入，不允许额外细化到格点之间。
            np.testing.assert_allclose(
                (angles + 60) / 0.2, np.round((angles + 60) / 0.2), atol=1e-10
            )
            assert trial.estimates[name].info["peak_refinement"] == "none"


@pytest.mark.parametrize(
    "refine,expected", [(None, "parabolic"), (True, "parabolic"), (False, "none")]
)
def test_v1_missing_and_explicit_refinement_keep_meaning(refine, expected, tmp_path):
    params = {} if refine is None else {"refine": refine}
    old = {
        "schema_version": 1,
        "algorithms": [{"id": "music", "params": params}],
        "trials": 1,
        "scenario": {"sources": {"angles": {"values": [-9.973, 10.027]}}},
    }
    before = json.dumps(old)
    config = ExperimentConfig.model_validate(old)
    assert json.dumps(old) == before
    assert config.schema_version == 2
    assert config.algorithms[0].params["peak_refinement"] == expected
    assert config.algorithms[0].params["grid_mode"] == "custom"
    assert config.algorithms[0].params["legacy_grid"] is True
    result = run_experiment(config)
    scene, array = build_scene(config)
    obs = scene.generate(RNGTree(config.scenario.seed).for_trial(0))
    grid = np.arange(-90, 90.05, 0.1)
    _, noise, _, _ = kit.subspace_decomposition(obs.covariance(), 2)
    spectrum = kit.music_spectrum(array.steering(grid), noise)
    spectrum /= spectrum.max()
    angles, _ = kit.peak_search(spectrum, grid, 2, min_separation=0.05)
    if expected == "parabolic":
        angles = kit.refine_peaks(spectrum, grid, angles)
    # 旧网格、旧寻峰和旧插值路径应逐值复现，不放宽成统计容差。
    np.testing.assert_array_equal(result.points[0].trials[0].estimates["music"].angles, angles)
    directory = tmp_path / "中文历史配置"
    ResultWriter(directory).write_experiment(result)
    restored = read_result(directory)
    assert restored.config["algorithms"][0]["params"]["peak_refinement"] == expected
    assert ExperimentConfig.model_validate(config.to_document()) == config


def test_custom_grid_and_shared_grid_sweep_are_explicit():
    config = ExperimentConfig(
        algorithms=[{"id": "music"}, {"id": "mvdr", "params": {"grid_step": 0.5}}],
        type="sweep",
        trials=1,
        sweep={"path": "search_grid.grid_step", "values": [0.1, 0.2]},
    )
    point = expand_point(config, 0.2)
    assert point.algorithms[0].params["grid_step"] == 0.2
    assert point.algorithms[1].params["grid_step"] == 0.5
    assert point.algorithms[1].params["grid_mode"] == "custom"
    config.sweep.path = "algorithms[0].params.grid_step"
    assert expand_point(config, 0.2).algorithms[0].params["grid_mode"] == "custom"
    assert config.algorithms[0].params["grid_step"] == 0.1
    # 普通外部插件即使有同名字段也不被框架重写。
    assert config.search_parameters(RootMUSIC, {"grid_step": 3}) == {"grid_step": 3}


@pytest.mark.parametrize("cls", [CBF, MVDR, MUSIC])
def test_local_variant_uses_real_spectrum_on_masked_array(cls):
    from dataclasses import replace

    array = make_array()
    mask = np.ones(16, dtype=bool)
    mask[3] = False
    array = replace(array, element_mask=mask)
    angles = np.array([12.037])
    rng = RNGTree(77).for_trial(0).for_noise()
    signal = rng.normal(size=(1, 1000)) + 1j * rng.normal(size=(1, 1000))
    X = array.steering(angles) @ signal
    X += (rng.normal(size=X.shape) + 1j * rng.normal(size=X.shape)) * 0.001
    obs = Observation(X, K=1)
    ctx = make_context()
    algo = cls()
    algo.configure(cls.Params(peak_refinement="local_dense"), array, ctx)
    actual = algo.estimate(obs, ctx)
    # 高 SNR 单信源排除波束重叠，0.002° 覆盖有限样本误差。
    np.testing.assert_allclose(actual.angles, angles, atol=0.002)
    assert actual.info["peak_refinement"] == "local_dense"
    assert actual.info["n_peaks_found"] == 1


def test_local_music_respects_spatial_smoothing_and_scan_boundaries():
    from arena.core.scenario.generator import generate_trial_data

    array, ctx = make_array(), make_context()
    truth = np.array([-3.027, 3.043])
    obs = generate_trial_data(array, truth, 2, 1000, 40, correlation_mode="coherent", seed=42)
    algo = MUSIC()
    algo.configure(
        MUSIC.Params(smoothing="fb", subarray=12, peak_refinement="local_dense"), array, ctx
    )
    np.testing.assert_allclose(algo.estimate(obs, ctx).angles, truth, atol=0.01)
    grid = np.arange(-1.0, 1.01, 0.1)
    called = []

    def evaluate(x):
        called.extend(x)
        return -((x - 0.937) ** 2)

    peaks = kit.refine_spectrum_peaks(
        -((grid - 0.937) ** 2), grid, np.array([0.9]), "local_dense", evaluate, 0.0001
    )
    np.testing.assert_allclose(peaks, [0.937], atol=0.000051)
    assert min(called) >= -1 and max(called) <= 1.00000001
    assert (
        len(kit.refine_spectrum_peaks(grid, grid, np.array([]), "local_dense", evaluate, 0.0001))
        == 0
    )


def test_grid_validation_and_conflicting_legacy_options():
    with pytest.raises(ValueError, match="冲突"):
        MUSIC.Params(refine=True, peak_refinement="none")
    with pytest.raises(ValueError, match="整除"):
        ExperimentConfig(search_grid={"grid_step": 0.7})
    with pytest.raises(ValueError, match="终止步长"):
        MUSIC.Params(peak_refinement="local_dense", local_step=1)
    legacy = ExperimentConfig(
        schema_version=1, algorithms=[{"id": "music", "params": {"grid_step": 0.7}}]
    )
    assert legacy.algorithms[0].params["legacy_grid"]
    assert SpectrumSearchParams(refine=False).peak_refinement == "none"


def test_local_refinement_keeps_two_nearby_peaks_distinct():
    from arena.core.scenario.generator import generate_trial_data

    array, ctx = make_array(), make_context()
    truth = np.array([-0.327, 0.343])
    obs = generate_trial_data(array, truth, 2, 2000, 50, seed=81)
    algo = MUSIC()
    algo.configure(MUSIC.Params(peak_refinement="local_dense"), array, ctx)
    estimate = algo.estimate(obs, ctx)
    assert estimate.info["n_peaks_found"] == 2
    np.testing.assert_allclose(estimate.angles, truth, atol=0.01)


def test_schema_and_normalize_expose_new_defaults_and_preserve_legacy():
    schema = asyncio.run(experiment_schema())
    assert schema["x-default"]["schema_version"] == 2
    assert schema["$defs"]["SearchGrid"]["properties"]["grid_step"]["default"] == 0.1
    for plugin in schema["x-algorithms"]:
        if plugin["id"] in {"cbf", "mvdr", "music"}:
            fields = plugin["schema"]["properties"]
            assert fields["peak_refinement"]["default"] == "none"
            assert fields["peak_refinement"]["x-summary"]
            assert fields["local_step"]["x-visible-when"] == {"peak_refinement": "local_dense"}
    old = asyncio.run(
        normalize_configuration({"schema_version": 1, "algorithms": [{"id": "music"}]})
    )
    assert old.algorithms[0].params["peak_refinement"] == "parabolic"


def test_normalize_invalid_draft_reports_field_without_mutating_input():
    from fastapi import HTTPException

    draft = {"type": "sweep", "sweep": {"path": "scenario.sources.snr_db", "values": []}}
    before = json.dumps(draft)
    with pytest.raises(HTTPException) as failure:
        asyncio.run(normalize_configuration(draft))
    assert failure.value.status_code == 400
    assert failure.value.detail["errors"][0]["path"] == "sweep.values"
    assert json.dumps(draft) == before
    draft["sweep"]["values"] = [-10, -5, 0, 5, 10, 15, 20]
    assert asyncio.run(normalize_configuration(draft)).sweep.values == draft["sweep"]["values"]


def test_invalid_algorithm_parameter_reports_algorithm_index():
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as failure:
        asyncio.run(
            normalize_configuration({"algorithms": [{"id": "music", "params": {"grid_step": -1}}]})
        )
    assert failure.value.detail["errors"][0]["path"] == "algorithms.0.params.grid_step"
