"""执行选项必须改变实际行为，不能只出现在 Schema 中。"""

import numpy as np
import pytest

from arena.core.config import ExperimentConfig
from arena.core.runner.core import run_experiment
from arena.core.storage import ResultWriter
from arena.core.storage.reader import read_result


@pytest.mark.parametrize("method", ["mdl", "aic"])
def test_source_count_estimation(method):
    config = ExperimentConfig.model_validate(
        {
            "type": "single",
            "trials": 1,
            "algorithms": [{"id": "music"}],
            "scenario": {"snapshots": 1000, "sources": {"snr_db": 30}},
            "options": {"source_count": method},
        }
    )
    trial = run_experiment(config).points[0].trials[0]
    assert trial.source_count == 2
    assert trial.estimates["music"].K_hat == 2


def test_save_options_and_roundtrip(tmp_path):
    config = ExperimentConfig.model_validate(
        {
            "type": "single",
            "trials": 1,
            "algorithms": [{"id": "music"}],
            "options": {"save_spectra": "none"},
        }
    )
    result = run_experiment(config)
    trial = result.points[0].trials[0]
    assert trial.estimates["music"].spectrum is None
    assert trial.observation.shape == (16, 200)
    ResultWriter(tmp_path).write_experiment(result)
    recovered = read_result(tmp_path)
    np.testing.assert_array_equal(recovered.points[0].trials[0].observation, trial.observation)
    assert recovered.points[0].trials[0].estimates["music"].info == trial.estimates["music"].info


def test_save_all_spectra_and_disable_estimates(tmp_path):
    config = ExperimentConfig.model_validate(
        {
            "trials": 2,
            "algorithms": [{"id": "music"}],
            "options": {"save_spectra": "all", "save_estimates": False},
        }
    )
    result = run_experiment(config)
    assert all(t.estimates["music"].spectrum is not None for t in result.points[0].trials)
    ResultWriter(tmp_path).write_experiment(result)
    with np.load(tmp_path / "results.npz", allow_pickle=False) as saved:
        assert not any(key.endswith("__estimates") for key in saved.files)
        assert "spectrum__0__1__music__values" in saved


def test_recompute_keeps_raw_results(tmp_path):
    import numpy as np

    import arena

    result = arena.run(
        {"type": "single", "trials": 1, "algorithms": [{"id": "music"}]}, workspace=tmp_path
    )
    directory = tmp_path / "experiments" / result.metadata["experiment_id"]
    with np.load(directory / "results.npz", allow_pickle=False) as raw:
        before = raw["estimates"].copy()
    updated = arena.recompute_metrics(
        directory, {"params": {"success_rate": {"threshold_deg": 0.00001}}}
    )
    assert updated.config["metrics"]["params"]["success_rate"]["threshold_deg"] == 0.00001
    assert updated.metadata["history"][-1]["action"] == "recompute_metrics"
    with np.load(directory / "results.npz", allow_pickle=False) as raw:
        np.testing.assert_array_equal(raw["estimates"], before)
        assert raw["metric__success_rate__value"][0, 0] == 0


def test_failed_estimates_penalty():
    from arena.core.metrics.compute import compute_metrics
    from arena_api import Estimate

    metric = compute_metrics(
        [Estimate.from_angles([10])], np.array([-10.0, 10.0]), include_failed=True, penalty_deg=90
    )
    assert metric["rmse_mean"] == pytest.approx(90 / np.sqrt(2))
    assert metric["num_valid"] == 1


def test_batch_called_with_independent_trial_rng(monkeypatch):
    from arena_api import Algorithm, Capabilities, Estimate

    calls = []

    class BatchProbe(Algorithm):
        id = "batch_probe"
        name = "批量探针"
        version = "1.0.0"
        capabilities = Capabilities(batch=True)

        def estimate(self, obs, ctx):
            return Estimate.from_angles([ctx.rng.uniform(-80, 80)])

        def estimate_batch(self, observations, ctx):
            calls.append(len(observations))
            return [
                Estimate.from_angles([ctx.rng_for(i).uniform(-80, 80)])
                for i, _ in enumerate(observations)
            ]

    config = ExperimentConfig.model_validate(
        {
            "trials": 5,
            "algorithms": [{"id": "batch_probe"}],
            "options": {"warmup": False, "chunk_size": 3},
        }
    )
    batch = run_experiment(config, algorithm_classes={"batch_probe": BatchProbe})
    assert calls == [3, 2]
    monkeypatch.setattr(BatchProbe, "capabilities", Capabilities(batch=False))
    serial = run_experiment(config, algorithm_classes={"batch_probe": BatchProbe})
    for first, second in zip(batch.points[0].trials, serial.points[0].trials):
        np.testing.assert_array_equal(
            first.estimates["batch_probe"].angles, second.estimates["batch_probe"].angles
        )


def test_partial_noncontiguous_trial_indices_roundtrip(tmp_path):
    config = ExperimentConfig.model_validate({"trials": 5, "algorithms": [{"id": "music"}]})
    result = run_experiment(config)
    result.points[0].trials = [result.points[0].trials[i] for i in [2, 4]]
    result.points[0].trials[0].errors["probe"] = "第二次试验错误"
    ResultWriter(tmp_path).write_experiment(result)
    recovered = read_result(tmp_path)
    assert [t.trial_idx for t in recovered.points[0].trials] == [2, 4]
    assert recovered.points[0].trials[0].errors["probe"] == "第二次试验错误"


def test_summary_figures_without_saved_estimates(tmp_path):
    from arena.core.figures.presentation import build_figures
    from arena.core.metrics.summary import point_metrics

    config = ExperimentConfig.model_validate(
        {"trials": 2, "algorithms": [{"id": "music"}], "options": {"save_estimates": False}}
    )
    result = run_experiment(config)
    expected = point_metrics(result, result.points[0], "music")
    ResultWriter(tmp_path).write_experiment(result)
    recovered = read_result(tmp_path)
    assert point_metrics(recovered, recovered.points[0], "music") == expected
    assert build_figures(recovered)["RMSE"].data[0].y[0] == expected["rmse_mean"]
