"""实验相关路由。"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse, StreamingResponse

from ...core.config import ExperimentConfig
from ...core.config.scenario import ArrayConfig, ImpairmentConfig
from ..contracts import (
    ChartList,
    ExperimentNotes,
    ResultDetails,
    ResultFiles,
    TaskList,
    TaskResponse,
    ValidationResult,
)
from ..tasks import Task, get_task_manager

logger = logging.getLogger(__name__)

router = APIRouter()


def _task_or_404(task_id: str) -> Task:
    task = get_task_manager().tasks.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    return task


@router.get("/experiments/tasks/{task_id}/notes", response_model=ExperimentNotes)
async def get_notes(task_id: str) -> ExperimentNotes:
    """读取独立备注文件，旧实验使用配置中的初始标签。"""
    task = _task_or_404(task_id)
    path = task.result_path / "notes.json" if task.result_path else None
    if path and path.exists():
        return ExperimentNotes.model_validate_json(path.read_text(encoding="utf-8"))
    return ExperimentNotes(tags=task.config.tags)


@router.put("/experiments/tasks/{task_id}/notes", response_model=ExperimentNotes)
async def update_notes(task_id: str, notes: ExperimentNotes) -> ExperimentNotes:
    """改名、备注、标签和收藏只写 notes.json，不改变原实验配置。"""
    from datetime import datetime

    from ...core.storage import ResultWriter

    task = _task_or_404(task_id)
    if task.result_path is None:
        raise HTTPException(status_code=400, detail="实验目录尚未创建")
    notes.updated_at = datetime.now().astimezone().isoformat()
    ResultWriter(task.result_path)._write_json(
        task.result_path / "notes.json", notes.model_dump(mode="json")
    )
    get_task_manager()._save_index()
    return notes


async def _prepare_config(config: dict[str, Any]) -> tuple[ExperimentConfig, list[dict[str, Any]]]:
    """绑定四类插件的真实来源，并在核心进程校验。"""
    # 解析配置
    exp_config = ExperimentConfig(**config)
    exp_config.validate_experiment()
    from .algorithms import list_algorithms

    plugins = await list_algorithms()
    discovered = {item["id"]: item for item in plugins["algorithms"]}
    for algorithm in exp_config.algorithms:
        if algorithm.id not in discovered:
            raise ValueError(f"算法 {algorithm.id} 未注册，请刷新算法库")
        if discovered[algorithm.id]["type"] == "external":
            algorithm.origin = discovered[algorithm.id]["origin"]
    targets: list[tuple[ArrayConfig | ImpairmentConfig, str]] = [
        (exp_config.scenario.array, "arrays"),
        *((item, "impairments") for item in exp_config.scenario.impairments),
    ]
    for item, kind in targets:
        entries = {record["id"]: record for record in plugins[kind]}
        if item.type not in entries:
            raise ValueError(f"插件 {item.type} 未注册，请刷新插件来源")
        item.origin = entries[item.type]["origin"]
    metric_entries = {record["id"]: record for record in plugins["metrics"]}
    for identifier in exp_config.metrics.include:
        if identifier == "crb":
            continue
        name = "resolution_prob" if identifier == "resolution" else identifier
        if name not in metric_entries:
            raise ValueError(f"指标 {name} 未注册，请刷新插件来源")
        if metric_entries[name]["origin"]:
            exp_config.metrics.origins[name] = metric_entries[name]["origin"]
    from ...core.operations import invoke

    checked = await asyncio.to_thread(
        invoke,
        "validate",
        {
            "config": exp_config.model_dump(mode="json"),
            "workspace": str(get_task_manager().output_dir.resolve()),
        },
    )
    return exp_config, checked["issues"]


@router.post(
    "/experiments/validate", response_model=ValidationResult, response_model_exclude_none=True
)
async def validate_experiment(config: dict[str, Any]) -> dict[str, Any]:
    """草稿静态检查，不创建任务或写入实验。"""
    try:
        parsed, issues = await _prepare_config(config)
        return {"valid": True, "issues": issues, "config": parsed.model_dump(mode="json")}
    except ValueError as exc:
        return {"valid": False, "issues": [{"level": "error", "message": str(exc)}]}


@router.post("/experiments/run")
async def run_experiment(
    config: dict[str, Any],
    background_tasks: BackgroundTasks,
) -> dict[str, Any]:
    """运行实验。

    Args:
        config: 实验配置（JSON）
        background_tasks: 后台任务

    Returns:
        任务信息
    """
    try:
        exp_config, _ = await _prepare_config(config)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"配置错误: {exc}") from exc

    # 创建任务
    task_manager = get_task_manager()
    task_id = task_manager.create_task(exp_config)

    # 后台运行
    background_tasks.add_task(task_manager.run_task, task_id)

    return {
        "task_id": task_id,
        "status": "created",
        "message": "实验已提交",
    }


@router.get(
    "/experiments/tasks/{task_id}", response_model=TaskResponse, response_model_exclude_none=True
)
async def get_task_status(task_id: str) -> dict[str, Any]:
    """查询任务状态。

    Args:
        task_id: 任务 ID

    Returns:
        任务状态
    """
    task_manager = get_task_manager()
    status = task_manager.get_task_status(task_id)

    if status is None:
        raise HTTPException(status_code=404, detail="任务不存在")

    return status


@router.get("/experiments/tasks/{task_id}/progress")
async def stream_progress(task_id: str) -> StreamingResponse:
    """实时进度推送（SSE）。

    Args:
        task_id: 任务 ID

    Returns:
        SSE 流
    """
    task_manager = get_task_manager()

    # 检查任务是否存在
    if task_id not in task_manager.tasks:
        raise HTTPException(status_code=404, detail="任务不存在")

    async def event_generator() -> AsyncIterator[str]:
        """SSE 事件生成器。"""
        queue = await task_manager.subscribe_progress(task_id)

        try:
            while True:
                # 获取进度消息
                message = await queue.get()

                # 格式化为 SSE
                import json

                data = json.dumps(message)
                yield f"data: {data}\n\n"

                # 如果任务完成，结束流
                if message["status"] in ["completed", "failed", "cancelled", "interrupted"]:
                    break

                # 避免过于频繁
                await asyncio.sleep(0.1)

        finally:
            await task_manager.unsubscribe_progress(task_id, queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@router.get("/experiments/tasks", response_model=TaskList, response_model_exclude_none=True)
async def list_tasks() -> dict[str, Any]:
    """列出所有任务。

    Returns:
        任务列表
    """
    task_manager = get_task_manager()
    tasks = task_manager.list_tasks()

    return {"tasks": tasks}


@router.delete("/experiments/tasks/{task_id}")
async def cancel_task(task_id: str) -> dict[str, Any]:
    """取消任务。

    Args:
        task_id: 任务 ID

    Returns:
        取消结果
    """
    task_manager = get_task_manager()
    task = task_manager.tasks.get(task_id)
    if (
        task
        and task.status in {"completed", "failed", "cancelled", "interrupted"}
        and task.result_path
    ):
        trash_dir = task_manager.output_dir / ".trash"
        trash_dir.mkdir(exist_ok=True)
        if task.result_path.exists():
            task.result_path.replace(trash_dir / task.result_path.name)
        task_manager.tasks.pop(task_id, None)
        task_manager._save_index()
        return {"message": "实验已移入回收站"}

    success = task_manager.cancel_task(task_id)

    if not success:
        raise HTTPException(status_code=404, detail="任务不存在或已完成")

    return {"message": "任务已取消"}


@router.post("/experiments/tasks/{task_id}/copy")
async def copy_task(task_id: str) -> dict[str, Any]:
    """复制任务配置，返回新的待运行任务。"""
    task = _task_or_404(task_id)
    new_id = get_task_manager().create_task(task.config.model_copy(deep=True))
    return {"task_id": new_id, "status": "created"}


@router.post("/experiments/tasks/{task_id}/rerun")
async def rerun_task(task_id: str, background_tasks: BackgroundTasks) -> dict[str, Any]:
    """使用原配置创建并启动新任务。"""
    task = _task_or_404(task_id)
    task_manager = get_task_manager()
    new_id = task_manager.create_task(task.config.model_copy(deep=True))
    background_tasks.add_task(task_manager.run_task, new_id)
    return {"task_id": new_id, "status": "created"}


@router.get(
    "/experiments/tasks/{task_id}/result",
    response_model=ResultFiles,
    response_model_exclude_none=True,
)
async def get_task_result(task_id: str) -> dict[str, Any]:
    """获取任务结果路径。

    Args:
        task_id: 任务 ID

    Returns:
        结果路径
    """
    task = _task_or_404(task_id)

    if task.result_path is None:
        raise HTTPException(status_code=400, detail="任务尚未形成结果，中断实验请先整理部分结果")
    if not (task.result_path / "results.npz").exists():
        raise HTTPException(status_code=400, detail="尚未保存完整试验块，请重新运行")

    return {
        "task_id": task_id,
        "result_path": str(task.result_path),
        "files": [
            "config.json",
            "meta.json",
            "results.npz",
            "summary.json",
        ],
    }


@router.get(
    "/experiments/tasks/{task_id}/charts",
    response_model=ChartList,
    response_model_exclude_none=True,
)
async def get_task_charts(task_id: str) -> dict[str, Any]:
    """读取实验汇总并转换为前端图表数据。"""
    task = _task_or_404(task_id)
    if task.result_path is None or not (task.result_path / "results.npz").exists():
        raise HTTPException(status_code=400, detail="第一个完整试验块保存后可查看图表")

    from ...core.operations import invoke

    return await asyncio.to_thread(invoke, "charts", {"directory": str(task.result_path)})


@router.get("/experiments/tasks/{task_id}/details", response_model=ResultDetails)
async def get_result_details(task_id: str) -> dict[str, Any]:
    """读取核心汇总的结果表与版本信息。"""
    task = _task_or_404(task_id)
    if task.result_path is None or not (task.result_path / "results.npz").exists():
        raise HTTPException(status_code=400, detail="尚无保存的结果")
    from ...core.operations import invoke

    return await asyncio.to_thread(invoke, "details", {"directory": str(task.result_path)})


@router.get("/experiments/compare/export/{fmt}")
async def export_comparison(fmt: str, ids: str, metric: str, log: bool = False) -> FileResponse:
    """仅解析受管实验路径，图表构造在核心进程完成。"""
    from ...core.operations import invoke

    selected = [_task_or_404(identifier) for identifier in ids.split(",")]
    if not 2 <= len(selected) <= 4 or any(t.result_path is None for t in selected):
        raise HTTPException(status_code=400, detail="请选择 2–4 个有结果的实验")
    try:
        exported = await asyncio.to_thread(
            invoke,
            "compare_export",
            {
                "directories": [str(t.result_path) for t in selected],
                "metric": metric,
                "format": fmt,
                "log": log,
            },
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    from pathlib import Path

    path = Path(exported["path"])
    return FileResponse(path, filename=path.name)


@router.post("/experiments/tasks/{task_id}/finalize")
async def finalize_partial(task_id: str) -> dict[str, str]:
    """将中断实验的最后完整检查点整理为取消结果。"""
    from ...core.operations import invoke
    from ..tasks import TaskStatus

    task = _task_or_404(task_id)
    if task.status != TaskStatus.INTERRUPTED or task.result_path is None:
        raise HTTPException(status_code=400, detail="只有已中断的实验需要整理部分结果")
    try:
        await asyncio.to_thread(invoke, "finalize", {"directory": str(task.result_path)})
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    task.status = TaskStatus.CANCELLED
    task.error = None
    get_task_manager()._save_index()
    return {"message": "已整理最后完整检查点，可查看部分结果"}


@router.post("/experiments/tasks/{task_id}/recompute")
async def recompute_task(task_id: str, metrics: dict[str, Any]) -> dict[str, Any]:
    """使用保存的估计重算统计，原始估计文件保持不变。"""
    task = _task_or_404(task_id)
    if task.status != "completed" or task.result_path is None:
        raise HTTPException(status_code=400, detail="请等待实验完成后重算指标")
    from ...core.operations import invoke

    async with get_task_manager()._lock:
        try:
            updated = await asyncio.to_thread(
                invoke, "recompute", {"directory": str(task.result_path), "metrics": metrics}
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        task.config = ExperimentConfig.model_validate(updated["config"])
        task.result = None
        get_task_manager()._save_index()
    return {"message": "指标已重算，原始估计未改变", **updated}


@router.get("/experiments/tasks/{task_id}/export/{fmt}")
async def export_task(
    task_id: str,
    fmt: str,
    metric: str = "rmse",
    chart: str | None = None,
    style: str = "web",
    log: bool = False,
    style_options: str | None = None,
) -> FileResponse:
    """隔离执行导出，按指标和当前图表选择生成文件。"""
    import json
    from pathlib import Path

    from ...core.operations import invoke

    task = _task_or_404(task_id)
    if task.status not in {"completed", "cancelled"} or task.result_path is None:
        raise HTTPException(status_code=400, detail="任务尚未形成可导出的结果")
    try:
        exported = await asyncio.to_thread(
            invoke,
            "export",
            {
                "directory": str(task.result_path),
                "format": fmt.lower(),
                "metric": metric,
                "chart": chart,
                "style": style,
                "log": log,
                "style_options": json.loads(style_options) if style_options else None,
            },
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    output = Path(exported["path"])
    return FileResponse(output, filename=output.name)


@router.get("/experiments/tasks/{task_id}/report")
async def view_report(task_id: str) -> FileResponse:
    """在浏览器中打开自包含报告，支持打印为 PDF。"""
    exported = await export_task(task_id, "html")
    return FileResponse(exported.path, media_type="text/html")
