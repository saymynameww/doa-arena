"""版本化标准场景集、后台评测与排行榜路由。"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

from ...core.config import AlgorithmConfig, ExperimentConfig
from ..tasks import get_task_manager

router = APIRouter()


class SuiteList(BaseModel):
    """场景集列表；配置保持动态插件参数。"""

    suites: list[dict[str, Any]]


class BenchmarkRunRequest(BaseModel):
    """选择当前草稿中的算法运行指定场景集版本。"""

    suite_id: str
    version: str
    algorithms: list[AlgorithmConfig] = Field(min_length=1)
    scenarios: list[str] | None = None


class BenchmarkRunRecord(BaseModel):
    """关联普通实验的评测记录。"""

    run_id: str
    suite_id: str
    suite_version: str
    suite_hash: str
    created_at: str
    algorithms: list[AlgorithmConfig]
    experiments: dict[str, str]


class LeaderboardResponse(BaseModel):
    """按显式列排名的结果，每个数值关联实验。"""

    suite_id: str
    version: str
    columns: list[dict[str, Any]]
    rows: list[dict[str, Any]]
    revisions: list[dict[str, str]]
    failures: list[str]


async def _invoke(operation: str, **payload: Any) -> dict[str, Any]:
    from ...core.operations import invoke

    try:
        return await asyncio.to_thread(
            invoke,
            operation,
            {"workspace": str(get_task_manager().output_dir.resolve()), **payload},
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/benchmarks/suites", response_model=SuiteList)
@router.get("/leaderboard/scenarios", response_model=SuiteList)
async def list_scenarios() -> dict[str, Any]:
    """列出内置和工作目录的不可变场景集版本。"""
    return await _invoke("benchmark_suites")


@router.post("/benchmarks/suites")
async def import_suite(suite: dict[str, Any]) -> dict[str, Any]:
    """导入自定义 JSON 场景集，拒绝覆盖同版本内容。"""
    return await _invoke("benchmark_save", suite=suite)


@router.post("/benchmarks/runs", response_model=BenchmarkRunRecord)
async def run_suite(
    request: BenchmarkRunRequest, background_tasks: BackgroundTasks
) -> dict[str, Any]:
    """完整预检后排入普通实验队列，共用进度、取消及结果入口。"""
    from .algorithms import list_algorithms

    plugins = await list_algorithms()
    for algorithm in request.algorithms:
        if algorithm.origin is None:
            plugin = next((p for p in plugins["algorithms"] if p["id"] == algorithm.id), None)
            if plugin:
                algorithm.origin = plugin["origin"]
    record = await _invoke("benchmark_create", **request.model_dump(mode="json"))
    manager = get_task_manager()
    for identifier in record["experiments"].values():
        directory = manager.output_dir / "experiments" / identifier
        config = ExperimentConfig.model_validate_json(
            (directory / "config.json").read_text(encoding="utf-8")
        )
        manager.create_task(config, task_id=identifier)
        background_tasks.add_task(manager.run_task, identifier)
    return record


@router.get("/leaderboard", response_model=LeaderboardResponse)
async def get_leaderboard(
    suite_id: str, version: str, column: int = 0, revision: str | None = None
) -> dict[str, Any]:
    """只比较同一场景集版本，默认各算法取最新的完整场景记录。"""
    return await _invoke(
        "benchmark_leaderboard",
        suite_id=suite_id,
        version=version,
        column=column,
        revision=revision,
    )


@router.get("/benchmarks/runs")
async def list_runs() -> dict[str, Any]:
    """从普通任务状态汇总评测进度。"""
    manager = get_task_manager()
    records = []
    for path in sorted((manager.output_dir / "benchmarks/runs").glob("*.json"), reverse=True):
        record = json.loads(path.read_text(encoding="utf-8"))
        states = {}
        for name, identifier in record["experiments"].items():
            task = manager.tasks.get(identifier)
            if task:
                states[name] = {
                    "status": task.status.value,
                    "progress": task.progress,
                    "experiment_id": identifier,
                }
            else:
                status_path = manager.output_dir / "experiments" / identifier / "status.json"
                status = (
                    json.loads(status_path.read_text(encoding="utf-8"))
                    if status_path.exists()
                    else {"status": "missing"}
                )
                states[name] = {
                    "status": status.get("status"),
                    "progress": status,
                    "experiment_id": identifier,
                }
        records.append({**record, "states": states})
    return {"runs": records}
