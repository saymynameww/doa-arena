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
def client():
    """测试客户端。"""
    from arena.server.app import create_app

    app = create_app()
    return TestClient(app)


def test_health_check(client):
    """测试健康检查。"""
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


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
    assert status["status"] in ["pending", "running", "completed"]


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
