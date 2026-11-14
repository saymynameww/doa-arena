"""后台任务管理。

管理实验运行任务，支持并发和取消。
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Any

from ..core.config import ExperimentConfig
from ..core.runner import run_experiment

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    """任务状态。"""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Task:
    """任务信息。"""

    task_id: str
    config: ExperimentConfig
    status: TaskStatus
    created_at: float
    started_at: float | None = None
    completed_at: float | None = None
    error: str | None = None
    progress: dict[str, Any] | None = None


class TaskManager:
    """任务管理器。

    管理实验任务的生命周期。
    """

    def __init__(self) -> None:
        """初始化。"""
        self.tasks: dict[str, Task] = {}
        self._lock = asyncio.Lock()

    def create_task(self, config: ExperimentConfig) -> str:
        """创建任务。

        Args:
            config: 实验配置

        Returns:
            任务 ID
        """
        task_id = str(uuid.uuid4())

        task = Task(
            task_id=task_id,
            config=config,
            status=TaskStatus.PENDING,
            created_at=time.time(),
        )

        self.tasks[task_id] = task
        logger.info(f"任务已创建: {task_id}")

        return task_id

    async def run_task(self, task_id: str) -> None:
        """运行任务（异步）。

        Args:
            task_id: 任务 ID
        """
        task = self.tasks.get(task_id)
        if task is None:
            logger.error(f"任务不存在: {task_id}")
            return

        # 更新状态
        task.status = TaskStatus.RUNNING
        task.started_at = time.time()
        logger.info(f"任务开始: {task_id}")

        try:
            # 在线程池中运行（避免阻塞事件循环）
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                run_experiment,
                task.config,
            )

            # 完成
            task.status = TaskStatus.COMPLETED
            task.completed_at = time.time()
            logger.info(f"任务完成: {task_id}")

        except Exception as e:
            logger.error(f"任务失败: {task_id}, 错误: {e}")
            task.status = TaskStatus.FAILED
            task.error = str(e)
            task.completed_at = time.time()

    def get_task_status(self, task_id: str) -> dict[str, Any] | None:
        """查询任务状态。

        Args:
            task_id: 任务 ID

        Returns:
            任务状态，不存在返回 None
        """
        task = self.tasks.get(task_id)
        if task is None:
            return None

        status = {
            "task_id": task.task_id,
            "status": task.status.value,
            "created_at": task.created_at,
        }

        if task.started_at:
            status["started_at"] = task.started_at

        if task.completed_at:
            status["completed_at"] = task.completed_at
            status["elapsed_seconds"] = task.completed_at - task.started_at

        if task.error:
            status["error"] = task.error

        if task.progress:
            status["progress"] = task.progress

        return status

    def list_tasks(self) -> list[dict[str, Any]]:
        """列出所有任务。

        Returns:
            任务列表
        """
        return [
            self.get_task_status(task_id)
            for task_id in sorted(
                self.tasks.keys(),
                key=lambda tid: self.tasks[tid].created_at,
                reverse=True,
            )
        ]

    def cancel_task(self, task_id: str) -> bool:
        """取消任务。

        Args:
            task_id: 任务 ID

        Returns:
            是否成功取消
        """
        task = self.tasks.get(task_id)
        if task is None or task.status not in [
            TaskStatus.PENDING,
            TaskStatus.RUNNING,
        ]:
            return False

        task.status = TaskStatus.CANCELLED
        task.completed_at = time.time()
        logger.info(f"任务已取消: {task_id}")

        return True


# 全局任务管理器实例
_task_manager: TaskManager | None = None


def get_task_manager() -> TaskManager:
    """获取任务管理器实例。

    Returns:
        TaskManager 实例
    """
    global _task_manager
    if _task_manager is None:
        _task_manager = TaskManager()
    return _task_manager
