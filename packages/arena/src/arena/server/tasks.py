"""后台任务管理。

管理实验运行任务，支持并发、取消和进度跟踪。
"""

from __future__ import annotations

import asyncio
import logging
import multiprocessing as mp
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from ..core.config import ExperimentConfig

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
    progress: dict[str, Any] = field(default_factory=dict)
    result_path: Path | None = None
    process: mp.Process | None = None


class TaskManager:
    """任务管理器。

    管理实验任务的生命周期，支持进度跟踪和订阅。
    """

    def __init__(self, output_dir: Path | None = None) -> None:
        """初始化。

        Args:
            output_dir: 结果输出目录
        """
        self.tasks: dict[str, Task] = {}
        self.output_dir = output_dir or Path("experiments")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock()
        self._progress_subscribers: dict[str, list[asyncio.Queue]] = {}

    def create_task(self, config: ExperimentConfig) -> str:
        """创建任务。

        Args:
            config: 实验配置

        Returns:
            任务 ID
        """
        task_id = str(uuid.uuid4())[:8]  # 短 ID

        # 结果路径
        result_path = self.output_dir / task_id

        task = Task(
            task_id=task_id,
            config=config,
            status=TaskStatus.PENDING,
            created_at=time.time(),
            result_path=result_path,
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

        # 初始化进度
        task.progress = {
            "current_point": 0,
            "total_points": 1,
            "current_trial": 0,
            "total_trials": task.config.trials,
            "completed_trials": 0,
            "percent": 0,
        }

        await self._notify_progress(task_id)

        try:
            # 在线程池中运行（避免阻塞事件循环）
            loop = asyncio.get_event_loop()

            # 创建进度回调
            async def progress_callback(current_trial: int, total_trials: int):
                task.progress["current_trial"] = current_trial
                task.progress["completed_trials"] = current_trial
                task.progress["percent"] = int(
                    (current_trial / total_trials) * 100
                )
                await self._notify_progress(task_id)

            # 运行实验
            result = await loop.run_in_executor(
                None,
                self._run_experiment_sync,
                task,
            )

            # 完成
            task.status = TaskStatus.COMPLETED
            task.completed_at = time.time()
            task.progress["percent"] = 100
            await self._notify_progress(task_id)

            logger.info(f"任务完成: {task_id}")

        except Exception as e:
            logger.error(f"任务失败: {task_id}, 错误: {e}")
            task.status = TaskStatus.FAILED
            task.error = str(e)
            task.completed_at = time.time()
            await self._notify_progress(task_id)

    def _run_experiment_sync(self, task: Task):
        """同步运行实验（在线程池中）。"""
        from ..core.runner import run_experiment
        from ..core.storage import ResultWriter

        # 运行实验
        result = run_experiment(task.config)

        # 保存结果
        writer = ResultWriter(task.result_path)
        writer.write_experiment(result)

        return result

    async def subscribe_progress(self, task_id: str) -> asyncio.Queue:
        """订阅任务进度。

        Args:
            task_id: 任务 ID

        Returns:
            进度消息队列
        """
        if task_id not in self._progress_subscribers:
            self._progress_subscribers[task_id] = []

        queue: asyncio.Queue = asyncio.Queue()
        self._progress_subscribers[task_id].append(queue)

        # 发送当前状态
        task = self.tasks.get(task_id)
        if task:
            await queue.put(self._format_progress(task))

        return queue

    async def unsubscribe_progress(self, task_id: str, queue: asyncio.Queue):
        """取消订阅。

        Args:
            task_id: 任务 ID
            queue: 消息队列
        """
        if task_id in self._progress_subscribers:
            try:
                self._progress_subscribers[task_id].remove(queue)
            except ValueError:
                pass

    async def _notify_progress(self, task_id: str):
        """通知进度订阅者。"""
        if task_id not in self._progress_subscribers:
            return

        task = self.tasks.get(task_id)
        if not task:
            return

        message = self._format_progress(task)

        # 发送给所有订阅者
        for queue in self._progress_subscribers[task_id]:
            try:
                await queue.put(message)
            except Exception as e:
                logger.error(f"进度通知失败: {e}")

    def _format_progress(self, task: Task) -> dict[str, Any]:
        """格式化进度消息。"""
        return {
            "task_id": task.task_id,
            "status": task.status.value,
            "progress": task.progress,
            "elapsed_seconds": (
                time.time() - task.started_at if task.started_at else 0
            ),
        }

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
