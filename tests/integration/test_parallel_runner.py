"""spawn 并行不能改变按种子派生的逐次结果。"""

import numpy as np
import pytest

from arena.core.config import ExperimentConfig
from arena.core.runner.core import run_experiment
from arena_api import Algorithm


class FailingProbe(Algorithm):
    """模块级探针供 spawn 导入，验证错误上限。"""

    id = "failing_probe"
    name = "失败探针"
    version = "1.0.0"

    def estimate(self, obs, ctx):
        raise ValueError("故意失败")


def test_parallel_error_limit_matches_serial():
    config = ExperimentConfig.model_validate(
        {
            "trials": 8,
            "algorithms": [{"id": "failing_probe"}, {"id": "music"}],
            "options": {"chunk_size": 2, "max_consecutive_errors": 3, "warmup": False},
        }
    )
    classes = {"failing_probe": FailingProbe}
    serial = run_experiment(config, algorithm_classes=classes)
    config.options.workers = 2
    parallel = run_experiment(config, algorithm_classes=classes)
    assert [t.errors for t in serial.points[0].trials] == [
        t.errors for t in parallel.points[0].trials
    ]
    assert all("music" in t.estimates for t in parallel.points[0].trials)


@pytest.mark.slow
def test_parallel_matches_serial():
    config = ExperimentConfig.model_validate(
        {
            "type": "sweep",
            "trials": 7,
            "sweep": {"path": "scenario.sources.snr_db", "values": [0, 10]},
            "scenario": {"sources": {"angles": {"mode": "random", "min": -50, "max": 50}}},
            "algorithms": [{"id": "music"}, {"id": "esprit"}],
            "options": {"chunk_size": 3, "common_random_numbers": False},
        }
    )
    serial = run_experiment(config)
    config.options.workers = 2
    parallel = run_experiment(config)
    assert parallel.metadata["workers"] == 2
    assert parallel.metadata["timing_note"] == "并行运行，计时仅供参考"
    for expected_point, actual_point in zip(serial.points, parallel.points):
        for expected, actual in zip(expected_point.trials, actual_point.trials):
            np.testing.assert_array_equal(expected.truth_angles, actual.truth_angles)
            for label in expected.estimates:
                np.testing.assert_array_equal(
                    expected.estimates[label].angles, actual.estimates[label].angles
                )
