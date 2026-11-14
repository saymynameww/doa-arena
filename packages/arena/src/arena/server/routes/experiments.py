"""实验相关路由。"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import StreamingResponse

from ...core.config import ExperimentConfig
from ..tasks import TaskManager, get_task_manager

logger = logging.getLogger(__name__)

router = APIRouter()


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
        # 解析配置
        exp_config = ExperimentConfig(**config)
        exp_config.validate_experiment()

    except Exception as e:
        logger.error(f"配置校验失败: {e}")
        raise HTTPException(status_code=400, detail=f"配置错误: {e}")

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


@router.get("/experiments/tasks/{task_id}")
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
async def stream_progress(task_id: str):
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

    async def event_generator():
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
                if message["status"] in ["completed", "failed", "cancelled"]:
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


@router.get("/experiments/tasks")
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
    success = task_manager.cancel_task(task_id)

    if not success:
        raise HTTPException(status_code=404, detail="任务不存在或已完成")

    return {"message": "任务已取消"}


@router.get("/experiments/tasks/{task_id}/result")
async def get_task_result(task_id: str) -> dict[str, Any]:
    """获取任务结果路径。

    Args:
        task_id: 任务 ID

    Returns:
        结果路径
    """
    task_manager = get_task_manager()
    task = task_manager.tasks.get(task_id)

    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")

    if task.status != "completed":
        raise HTTPException(status_code=400, detail="任务未完成")

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
