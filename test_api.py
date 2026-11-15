"""测试后端 API。"""

import time

import requests

BASE_URL = "http://127.0.0.1:8765/api"


def test_health():
    """健康检查。"""
    print("1. 健康检查...")
    response = requests.get(f"{BASE_URL}/health")
    print(f"   状态: {response.json()}")
    print()


def test_algorithms():
    """获取算法列表。"""
    print("2. 获取算法列表...")
    response = requests.get(f"{BASE_URL}/algorithms")
    algorithms = response.json()["algorithms"]
    print(f"   共 {len(algorithms)} 个算法:")
    for algo in algorithms:
        print(f"   - {algo['name']}: {algo['description']}")
    print()


def test_run_experiment():
    """运行实验。"""
    print("3. 提交实验...")

    config = {
        "name": "API 测试实验",
        "type": "monte_carlo",
        "trials": 10,
        "scenario": {"seed": 42, "snapshots": 50},
        "algorithms": [
            {"id": "music", "label": "MUSIC"},
            {"id": "esprit", "label": "ESPRIT"},
        ],
        "options": {},
    }

    response = requests.post(f"{BASE_URL}/experiments/run", json=config)
    result = response.json()
    task_id = result["task_id"]

    print(f"   任务 ID: {task_id}")
    print(f"   状态: {result['status']}")
    print()

    # 等待完成
    print("4. 监控进度...")
    while True:
        response = requests.get(f"{BASE_URL}/experiments/tasks/{task_id}")
        task = response.json()

        status = task["status"]
        progress = task.get("progress", {})
        percent = progress.get("percent", 0)

        print(f"   状态: {status}, 进度: {percent}%")

        if status in ["completed", "failed", "cancelled"]:
            break

        time.sleep(1)

    print()
    print(f"✓ 实验完成！")

    if status == "completed":
        print(f"  耗时: {task.get('elapsed_seconds', 0):.2f} 秒")


def test_history():
    """查看历史实验。"""
    print("\n5. 查看历史实验...")
    response = requests.get(f"{BASE_URL}/experiments/tasks")
    tasks = response.json()["tasks"]

    print(f"   共 {len(tasks)} 个任务:")
    for task in tasks[:5]:  # 只显示前 5 个
        print(
            f"   - {task['task_id']}: {task['status']} "
            f"({task.get('progress', {}).get('percent', 0)}%)"
        )
    print()


if __name__ == "__main__":
    print("=" * 60)
    print("Arena Web API 测试")
    print("=" * 60)
    print()

    try:
        test_health()
        test_algorithms()
        test_run_experiment()
        test_history()

        print("=" * 60)
        print("全部测试通过！")
        print("=" * 60)

    except Exception as e:
        print(f"错误: {e}")
        import traceback

        traceback.print_exc()
