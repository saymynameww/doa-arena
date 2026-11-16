"""排行榜与场景集路由。"""

import json
from typing import Any

from fastapi import APIRouter

from ..tasks import get_task_manager

router = APIRouter()


@router.get("/leaderboard/scenarios")
async def list_scenarios() -> dict[str, Any]:
    """从已完成实验配置生成可选场景集。"""
    manager = get_task_manager()
    scenarios = []
    seen: set[str] = set()
    for task in manager.tasks.values():
        if task.status.value != "completed" or task.config is None:
            continue
        scenario = task.config.scenario.model_dump(mode="json") if task.config.scenario else {}
        key = json.dumps(scenario, sort_keys=True, ensure_ascii=False)
        if key not in seen:
            seen.add(key)
            scenarios.append(
                {
                    "id": f"scenario-{len(scenarios) + 1}",
                    "name": f"场景 {len(scenarios) + 1}",
                    "config": scenario,
                }
            )
    return {"scenarios": scenarios}


@router.get("/leaderboard")
async def get_leaderboard() -> dict[str, Any]:
    """返回已完成实验的最佳 RMSE 排名。"""
    rows = []
    manager = get_task_manager()
    for task in manager.tasks.values():
        if task.status.value != "completed" or task.result_path is None:
            continue
        summary_path = task.result_path / "summary.json"
        if not summary_path.exists():
            continue
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        values = []
        for point in summary.get("points", []):
            for metrics in point.get("algorithms", {}).values():
                if metrics.get("rmse_mean") is not None:
                    values.append(float(metrics["rmse_mean"]))
        if values:
            rows.append(
                {
                    "task_id": task.task_id,
                    "name": task.config.name,
                    "rmse": min(values),
                    "status": "completed",
                }
            )
    rows.sort(key=lambda row: row["rmse"])
    for rank, row in enumerate(rows, start=1):
        row["rank"] = rank
    return {"rows": rows}
