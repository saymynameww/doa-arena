"""工作目录在服务重启后保持一致，避免模型路径和实验目录分离。"""

import pytest

pytest.importorskip("fastapi")


def test_restart_preserves_workspace_root(tmp_path, monkeypatch):
    from arena.core.config import ExperimentConfig
    from arena.core.facade import Workspace
    from arena.core.storage.writer import ResultWriter
    from arena.server import tasks
    from arena.server.routes import settings

    workspace = Workspace(tmp_path / "中文课题")
    selection = tmp_path / "current.json"
    ResultWriter(tmp_path)._write_json(selection, {"path": str(workspace.path)})
    monkeypatch.setattr(settings, "CURRENT_WORKSPACE_PATH", selection)
    monkeypatch.setattr(tasks, "_task_manager", None)
    manager = tasks.get_task_manager()
    assert manager.output_dir == workspace.path
    identifier = manager.create_task(
        ExperimentConfig.model_validate({"algorithms": [{"id": "music"}]})
    )
    assert manager.tasks[identifier].result_path == workspace.experiments / identifier
    monkeypatch.setattr(tasks, "_task_manager", None)
    restored = tasks.get_task_manager()
    assert identifier in restored.tasks
    assert restored.tasks[identifier].result_path == workspace.experiments / identifier
