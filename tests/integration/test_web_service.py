"""测试 Web 服务。"""

import pytest

# 检查依赖
try:
    from fastapi.testclient import TestClient

    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

pytestmark = pytest.mark.skipif(
    not HAS_FASTAPI,
    reason="FastAPI not installed",
)


@pytest.fixture
def client(tmp_path, monkeypatch):
    """测试客户端。"""
    from arena.server import tasks
    from arena.server.app import create_app
    from arena.server.routes import settings, templates

    for name in ("SETTINGS_PATH", "WORKSPACES_PATH", "CURRENT_WORKSPACE_PATH"):
        monkeypatch.setattr(settings, name, tmp_path / getattr(settings, name).name)
    monkeypatch.setattr(templates, "TEMPLATES_DIR", tmp_path / "templates")
    monkeypatch.setattr(tasks, "_task_manager", tasks.TaskManager(tmp_path / "results"))
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client


def test_health_check(client):
    """测试健康检查。"""
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_notes_do_not_mutate_experiment_config(client):
    """用户备注与计算配置分开存储，支持历史筛选和重建。"""
    from arena.server.tasks import get_task_manager

    response = client.post(
        "/api/experiments/run",
        json={
            "name": "原实验名",
            "trials": 1,
            "algorithms": [{"id": "music"}],
            "tags": ["initial"],
        },
    )
    identifier = response.json()["task_id"]
    config_path = get_task_manager().tasks[identifier].result_path / "config.json"
    before = config_path.read_bytes()
    notes = client.put(
        f"/api/experiments/tasks/{identifier}/notes",
        json={
            "display_name": "修改显示名",
            "notes": "科研备注",
            "tags": ["coherent"],
            "starred": True,
        },
    )
    assert notes.status_code == 200
    task = client.get(f"/api/experiments/tasks/{identifier}").json()
    assert task["name"] == "修改显示名"
    assert task["tags"] == ["coherent"]
    assert task["starred"] is True
    assert config_path.read_bytes() == before


def test_metric_recompute_api_preserves_raw(client):
    """通过接口重算后，历史图表更新且原始估计字节不变。"""
    import numpy as np

    from arena.server.tasks import get_task_manager

    response = client.post(
        "/api/experiments/run",
        json={
            "trials": 2,
            "algorithms": [{"id": "music"}],
        },
    )
    assert response.status_code == 200, response.text
    task_id = response.json()["task_id"]
    task = get_task_manager().tasks[task_id]
    raw_path = task.result_path / "results.npz"
    with np.load(raw_path, allow_pickle=False) as raw:
        before = raw["estimates"].copy()
    updated = client.post(
        f"/api/experiments/tasks/{task_id}/recompute",
        json={
            "params": {"success_rate": {"threshold_deg": 0.000001}},
        },
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["metadata"]["history"][-1]["action"] == "recompute_metrics"
    with np.load(raw_path, allow_pickle=False) as raw:
        np.testing.assert_array_equal(raw["estimates"], before)
        assert raw["metric__success_rate__value"][0, 0] == 0
    charts = client.get(f"/api/experiments/tasks/{task_id}/charts")
    assert charts.status_code == 200
    success = next(c for c in charts.json()["charts"] if c["title"] == "成功率")
    assert success["data"][0]["y"] == [0.0]


def test_run_experiment(client):
    """测试运行实验。"""
    # 配置
    config = {
        "name": "Web 测试",
        "type": "monte_carlo",
        "trials": 5,
        "scenario": {
            "seed": 42,
            "snapshots": 50,
        },
        "algorithms": [
            {"id": "music", "label": "MUSIC"},
        ],
        "options": {},
    }

    # 提交实验
    response = client.post("/api/experiments/run", json=config)

    assert response.status_code == 200
    data = response.json()
    assert "task_id" in data
    assert data["status"] == "created"

    task_id = data["task_id"]

    # 查询状态
    response = client.get(f"/api/experiments/tasks/{task_id}")
    assert response.status_code == 200

    status = response.json()
    assert status["task_id"] == task_id
    assert status["status"] in ["queued", "running", "completed"]


def test_list_tasks(client):
    """测试列出任务。"""
    # 先创建一个任务
    config = {
        "name": "列表测试",
        "trials": 3,
        "algorithms": [{"id": "music"}],
    }

    client.post("/api/experiments/run", json=config)

    # 列出任务
    response = client.get("/api/experiments/tasks")

    assert response.status_code == 200
    data = response.json()
    assert "tasks" in data
    assert len(data["tasks"]) > 0


def test_invalid_config(client):
    """测试无效配置。"""
    # 缺少必填字段
    config = {
        "name": "无效配置",
        # 缺少 algorithms
    }

    response = client.post("/api/experiments/run", json=config)

    assert response.status_code == 400
    assert "配置错误" in response.json()["detail"]


def test_get_nonexistent_task(client):
    """测试查询不存在的任务。"""
    response = client.get("/api/experiments/tasks/nonexistent-id")

    assert response.status_code == 404


def test_cancel_task(client):
    """测试取消任务。"""
    # 创建任务
    config = {
        "name": "取消测试",
        "trials": 100,  # 较长的任务
        "algorithms": [{"id": "music"}],
    }

    response = client.post("/api/experiments/run", json=config)
    task_id = response.json()["task_id"]

    # 取消任务
    response = client.delete(f"/api/experiments/tasks/{task_id}")

    # 可能已经完成，所以不一定成功
    assert response.status_code in [200, 404]


def test_list_algorithms(client):
    """测试列出算法。"""
    response = client.get("/api/algorithms")

    assert response.status_code == 200
    data = response.json()
    assert "algorithms" in data
    assert len(data["algorithms"]) > 0

    # 验证算法结构
    algo = data["algorithms"][0]
    assert "id" in algo
    assert "name" in algo
    assert "description" in algo


def test_experiment_schema(client):
    """实验 Schema 应包含算法和扫描变量声明。"""
    response = client.get("/api/schema/experiment")

    assert response.status_code == 200
    data = response.json()
    assert "properties" in data
    assert len(data["x-algorithms"]) >= 1
    assert {item["path"] for item in data["x-sweep-paths"]} >= {
        "scenario.sources.snr_db",
        "scenario.snapshots",
    }


def test_settings_and_templates(client):
    """设置和模板接口应支持持久化读写。"""
    settings = {"workDir": "D:/ArenaTests", "defaultTrials": 12}
    response = client.put("/api/settings", json=settings)
    assert response.status_code == 200
    assert client.get("/api/settings").json()["defaultTrials"] == 12

    template = {
        "name": "接口测试模板",
        "description": "测试模板",
        "type": "monte_carlo",
        "algorithms": ["music"],
    }
    response = client.post("/api/templates", json=template)
    assert response.status_code == 200
    template_id = response.json()["id"]

    response = client.put(
        f"/api/templates/{template_id}",
        json={**template, "name": "更新后的模板"},
    )
    assert response.status_code == 200
    assert response.json()["name"] == "更新后的模板"

    response = client.delete(f"/api/templates/{template_id}")
    assert response.status_code == 200


def test_workspace_selection_and_algorithm_refresh(client, tmp_path):
    """工作目录切换和算法刷新接口应返回可消费的状态。"""
    response = client.post("/api/workspaces", json={"name": "测试目录", "path": str(tmp_path)})
    assert response.status_code == 200
    response = client.put("/api/workspaces/current", json=response.json())
    assert response.status_code == 200
    assert client.get("/api/workspaces/current").json()["path"] == str(tmp_path)

    response = client.post("/api/algorithms/refresh")
    assert response.status_code == 200
    assert response.json()["failures"] == []
    assert len(response.json()["algorithms"]) >= 1


def test_leaderboard_endpoint(client):
    """排行榜接口在没有完成实验时也应返回稳定结构。"""
    response = client.get("/api/leaderboard")
    assert response.status_code == 200
    assert "rows" in response.json()
    response = client.get("/api/leaderboard/scenarios")
    assert response.status_code == 200
    assert "scenarios" in response.json()


def test_get_algorithm(client):
    """测试获取算法详情。"""
    response = client.get("/api/algorithms/music")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "music"
    assert "params" in data


def test_get_task_result(client):
    """测试获取任务结果。"""
    # 创建并运行任务
    config = {
        "name": "结果测试",
        "trials": 2,
        "algorithms": [{"id": "music"}],
    }

    response = client.post("/api/experiments/run", json=config)
    task_id = response.json()["task_id"]

    # 等待完成（简化：直接查询）
    import time

    time.sleep(2)

    # 获取结果
    response = client.get(f"/api/experiments/tasks/{task_id}/result")

    # 可能未完成
    if response.status_code == 200:
        data = response.json()
        assert "result_path" in data
        assert "files" in data


def test_preflight_warns_without_creating_task(client):
    from arena.server.tasks import get_task_manager

    response = client.post(
        "/api/experiments/validate",
        json={
            "algorithms": [{"id": "music"}],
            "scenario": {"sources": {"correlation": {"mode": "coherent"}}},
        },
    )
    assert response.status_code == 200
    assert response.json()["valid"]
    assert any(issue["level"] == "warning" for issue in response.json()["issues"])
    assert not get_task_manager().tasks


def test_templates_cannot_overwrite_builtin_or_escape_directory(client):
    for identifier, code in [("../escape", 400), ("standard-comparison", 409)]:
        response = client.post("/api/templates", json={"id": identifier, "name": "测试"})
        assert response.status_code == code


def test_web_workspace_uses_same_layout_as_script(client, tmp_path):
    from arena.server.tasks import get_task_manager

    root = tmp_path / "课题目录"
    response = client.put("/api/workspaces/current", json={"name": "课题", "path": str(root)})
    assert response.status_code == 200
    assert (root / "arena_workspace.json").exists()
    assert get_task_manager().output_dir == root / "experiments"
