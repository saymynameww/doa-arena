"""独立课题目录中的生成—训练—导出—评测链路，可在无显示器 Linux 运行。"""

import json
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.slow
def test_external_training_workflow(tmp_path):
    pytest.importorskip("torch")
    import arena

    root = Path(__file__).resolve().parents[2]
    project = tmp_path / "独立训练课题"
    created = subprocess.run(
        [sys.executable, str(root / "scripts/create_learning_example.py"), str(project)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )
    assert created.returncode == 0, created.stderr
    trained = subprocess.run(
        [sys.executable, "train.py", "--samples", "32", "--epochs", "1"],
        cwd=project,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
    )
    assert trained.returncode == 0, trained.stderr
    log = json.loads(trained.stdout.splitlines()[-1])
    assert len(log["losses"]) == 1 and log["losses"][0] > 0
    from arena.core.plugins import discover
    from arena.core.storage.writer import ResultWriter

    sources = [{"type": "path", "value": str(project / "algorithms"), "import_root": str(project)}]
    registry = discover(sources)
    assert not registry["failures"], registry["failures"]
    plugin = next(p for p in registry["algorithms"] if p["id"] == "cnn_grid_example")
    workspace = arena.Workspace(project / "arena_ws")
    ResultWriter(workspace.path)._write_json(
        workspace.path / "arena_workspace.json",
        {
            "schema_version": 1,
            "name": "训练测试",
            "algorithm_sources": sources,
        },
    )
    result = arena.run(
        {
            "trials": 3,
            "scenario": {"snapshots": 200},
            "algorithms": [
                {
                    "id": plugin["id"],
                    "origin": plugin["origin"],
                    "params": {"model": "models/cnn_demo", "device": "cpu", "batch_size": 2},
                }
            ],
        },
        workspace=workspace,
    )
    assert result.metadata["status"] == "completed"
    assert all(not trial.errors for point in result.points for trial in point.trials)
    saved = json.loads(
        (Path(result.metadata["directory"]) / "config.json").read_text(encoding="utf-8")
    )
    assert saved["algorithms"][0]["params"]["model"] == "models/cnn_demo"
    model = result.metadata["plugins"]["algorithm/cnn_grid_example"]["model"]
    assert model["weights_sha256"].startswith("sha256:")
    assert Path(model["path"]).is_absolute()
