"""重验中尚缺的逐源结果和脚本调试接口。"""

import numpy as np

import arena
from arena.core.algorithms import MUSIC


def test_per_source_arrays_and_recompute(tmp_path):
    result = arena.run({"trials": 3, "algorithms": [{"id": "music"}]}, workspace=tmp_path)
    directory = tmp_path / "experiments" / result.metadata["experiment_id"]
    with np.load(directory / "results.npz", allow_pickle=False) as raw:
        assert raw["crb_per_source"].shape == (1, 2)
        assert raw["metric__rmse__per_source"].shape == (1, 1, 2)
        matched = raw["matched"][0, 0]
        truth = raw["truth"][0]
        np.testing.assert_allclose(
            raw["metric__rmse__per_source"][0, 0],
            np.sqrt(np.mean((matched - truth) ** 2, axis=0)),
            rtol=1e-12,
        )
    arena.recompute_metrics(directory, {"params": {"success_rate": {"threshold_deg": 0.1}}})
    with np.load(directory / "results.npz", allow_pickle=False) as raw:
        assert "crb_per_source" in raw
        assert "metric__rmse__per_source" in raw


def test_scenario_sample_and_estimate_once_match_runner():
    scenario = arena.Scenario({"seed": 42})
    trial = scenario.sample(0)
    first = MUSIC().estimate_once(trial)
    second = MUSIC().estimate_once(scenario.sample(0))
    np.testing.assert_array_equal(first.angles, second.angles)
    assert trial.truth.angles.shape == (2,)


def test_spectrum_criterion_without_persisting_spectra(tmp_path):
    result = arena.run(
        {
            "trials": 3,
            "algorithms": [{"id": "music"}],
            "options": {"save_spectra": "none"},
            "metrics": {
                "include": ["resolution_prob", "bias", "detection_accuracy", "time"],
                "params": {"resolution_prob": {"criterion": "spectrum"}},
            },
        },
        workspace=tmp_path,
    )
    directory = tmp_path / "experiments" / result.metadata["experiment_id"]
    with np.load(directory / "results.npz", allow_pickle=False) as raw:
        assert not any(name.startswith("spectrum__") for name in raw.files)
        assert raw["resolved_by_spectrum"].shape == (1, 1, 3)
        assert raw["metric__resolution_prob__value"][0, 0] == 1
        assert raw["metric__detection_accuracy__value"][0, 0] == 1
        np.testing.assert_array_equal(
            raw["metric__time__value"], raw["metric__time__extra__median"]
        )
        assert raw["metric__bias__per_source"].shape == (1, 1, 2)


def test_checkpoint_point_files_and_finalize(tmp_path):
    from arena.core.config import ExperimentConfig
    from arena.core.runner import run_experiment
    from arena.core.storage import ResultWriter

    config = ExperimentConfig(trials=2, algorithms=[{"id": "music"}], options={"chunk_size": 1})
    writer = ResultWriter(tmp_path / "experiments" / "interrupted")
    result = run_experiment(config)
    result.metadata["status"] = "running"
    writer.write_experiment(result)
    point = writer.output_dir / "points" / "p_000.npz"
    assert point.exists()
    with np.load(point, allow_pickle=False) as raw:
        assert raw["truth"].shape == (2, 2)
        assert raw["status"].shape == (1, 2)
    (writer.output_dir / "results.npz").unlink()
    finalized = arena.finalize("interrupted", workspace=tmp_path)
    assert finalized.metadata["status"] == "cancelled"
    from arena.server.tasks import TaskManager

    restored = TaskManager(tmp_path).get_task_status("interrupted")
    assert restored["progress"]["completed_trials"] == 2
    assert restored["progress"]["total_trials"] == 2
    assert not (writer.output_dir / "points").exists()
    assert finalized.saved_summary["complete"] is False
    np.testing.assert_array_equal(
        finalized.points[0].trials[0].truth_angles, result.points[0].trials[0].truth_angles
    )


def test_known_failures_reach_algorithm_and_validate_capabilities():
    from arena.core.config import ExperimentConfig
    from arena.core.runner import run_experiment
    from arena_api import Algorithm, Estimate

    class MaskProbe(Algorithm):
        id = "mask_probe"
        name = "掩码探针"
        version = "1.0.0"

        def configure(self, params, array, ctx):
            self.mask = array.element_mask

        def estimate(self, obs, ctx):
            assert self.mask.tolist() == [True, False] + [True] * 14
            return Estimate.from_angles([-10, 10])

    config = ExperimentConfig(
        algorithms=[{"id": "mask_probe"}],
        scenario={
            "impairments": [{"type": "element_failure", "params": {"indices": [1], "known": True}}]
        },
    )
    result = run_experiment(config, algorithm_classes={"mask_probe": MaskProbe})
    assert not result.points[0].trials[0].errors


def test_selected_chart_export_and_script_figures(tmp_path):
    import json

    from arena.core.export.service import export_result

    result = arena.run({"trials": 2, "algorithms": [{"id": "music"}]}, workspace=tmp_path)
    directory = tmp_path / "experiments" / result.metadata["experiment_id"]
    path = export_result(directory, "html", chart="成功率")
    text = path.read_text(encoding="utf-8")
    assert json.dumps("成功率", ensure_ascii=True)[1:-1] in text
    assert '"metric":"success_rate"' in text
    assert 'src="https://cdn.plot.ly' not in text
    assert len(arena.figures.build(result, "success_rate").data) == 1
    result.to_latex_table("success_rate", path=tmp_path / "success.tex")
    manifest = json.loads((tmp_path / "arena_workspace.json").read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 1
    assert (directory / "log.txt").exists()
