"""数据格式规范中的随机信源和复杂相关系数回归。"""

import numpy as np
import pytest

from arena.core.config import ExperimentConfig
from arena.core.runner.core import build_scene


def test_weighted_source_count_and_complex_correlation():
    config = ExperimentConfig.model_validate(
        {
            "scenario": {
                "seed": 2**40,
                "sources": {
                    "K": {"choice": [1, 2], "weights": [0, 3]},
                    "angles": {"mode": "random", "min": -50, "max": 50},
                    "correlation": {"mode": "partial", "rho": {"mag": 0.5, "phase_deg": 30}},
                },
            },
        }
    )
    scene, _ = build_scene(config, 3)
    assert len(scene.config.angles) == 2
    covariance = scene.config.correlation.to_matrix()
    np.testing.assert_allclose(covariance[0, 1], 5 * np.exp(1j * np.pi / 6), rtol=1e-14)


def test_random_angles_match_rejection_sampling():
    config = ExperimentConfig.model_validate(
        {
            "scenario": {
                "seed": 42,
                "sources": {
                    "angles": {"mode": "random", "range_deg": [-20, 20], "min_separation": 10}
                },
            }
        }
    )
    rng = np.random.default_rng(np.random.SeedSequence(42, spawn_key=(9, 4)))
    for _ in range(10000):
        expected = np.sort(rng.uniform(-20, 20, 2))
        if np.min(np.diff(expected)) >= 10:
            break
    scene, _ = build_scene(config, 4)
    np.testing.assert_array_equal(scene.config.angles, expected)


@pytest.mark.parametrize(
    "distribution",
    [
        {"choice": [1, 2], "weights": [0, 0]},
        {"choice": [1, 2], "weights": [1]},
        {"uniform_int": [3, 1]},
    ],
)
def test_invalid_source_count_distribution(distribution):
    with pytest.raises(ValueError):
        ExperimentConfig.model_validate({"scenario": {"sources": {"K": distribution}}})


def test_normative_document_roundtrip():
    document = {
        "schema_version": 1,
        "name": "规范配置",
        "seed": 2**40,
        "tags": ["复现"],
        "scenario": {
            "carrier_hz": 3e9,
            "noise": "white_gaussian",
            "sources": {"signal": "gaussian"},
        },
        "algorithms": [{"id": "music"}],
        "experiment": {"type": "single", "trials": 1},
        "metrics": {"include": ["rmse", "resolution_prob"], "crb": True},
    }
    config = ExperimentConfig.model_validate(document)
    config.validate_experiment()
    assert config.type == "single"
    assert config.scenario.seed == 2**40
    exported = config.to_document()
    assert exported["seed"] == 2**40
    assert exported["experiment"]["type"] == "single"
    assert "seed" not in exported["scenario"]
    assert "crb" not in exported["metrics"]["include"]
    assert ExperimentConfig.model_validate(exported) == config
