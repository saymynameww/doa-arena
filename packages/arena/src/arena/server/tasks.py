"""后台任务管理。

管理实验运行任务，支持并发、取消和进度跟踪。
"""

from __future__ import annotations

import asyncio
import json
import logging
import multiprocessing as mp
import sqlite3
import time
import uuid
from contextlib import closing
from dataclasses import dataclass, field
from enum import Enum
from multiprocessing.process import BaseProcess
from pathlib import Path
from typing import Any

from ..core.config import ExperimentConfig
from ..core.runner.results import ExperimentResult

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    """任务状态。"""

    PENDING = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    INTERRUPTED = "interrupted"


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
    process: BaseProcess | None = None
    result: ExperimentResult | None = None


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
        self._index_path = self.output_dir / ".arena_index.sqlite"
        self._lock = asyncio.Lock()
        self._run_lock = asyncio.Lock()
        self._file_versions: dict[str, tuple[int, ...]] = {}
        self._progress_subscribers: dict[str, list[asyncio.Queue]] = {}
        self._load_index()
        self.rebuild_index()

    def _load_index(self) -> None:
        """从结果目录恢复历史任务元数据。"""
        if not self._index_path.exists():
            return
        try:
            with closing(sqlite3.connect(self._index_path)) as connection, connection:
                records = [
                    json.loads(row[0])
                    for row in connection.execute("SELECT record FROM experiments")
                ]

        except (OSError, json.JSONDecodeError, sqlite3.DatabaseError) as exc:
            logger.warning("读取任务索引失败，将从空列表开始: %s", exc)
            return
        for record in records if isinstance(records, list) else []:
            try:
                config = ExperimentConfig.model_validate(record["config"])
                raw_status = record.get("status", TaskStatus.FAILED.value)
                status = TaskStatus("queued" if raw_status == "pending" else raw_status)
                if status == TaskStatus.PENDING:
                    status = TaskStatus.CANCELLED
                task = Task(
                    task_id=record["task_id"],
                    config=config,
                    status=status,
                    created_at=float(record["created_at"]),
                    started_at=record.get("started_at"),
                    completed_at=record.get("completed_at"),
                    error=record.get("error"),
                    progress=record.get("progress", {}),
                    result_path=Path(record["result_path"]),
                )
                self.tasks[task.task_id] = task
            except (KeyError, TypeError, ValueError) as exc:
                logger.warning("跳过损坏的任务索引记录: %s", exc)

    def switch_output_dir(self, output_dir: Path) -> None:
        """切换后续任务的结果目录并加载该目录的历史索引。"""
        self.output_dir = output_dir.expanduser()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._index_path = self.output_dir / ".arena_index.sqlite"
        self.tasks.clear()
        self._file_versions.clear()
        self._load_index()
        self.rebuild_index()

    def rebuild_index(self, changed_only: bool = False) -> int:
        """从实验文件恢复历史，兼容旧目录和规范的 experiments 子目录。"""
        roots = [
            self.output_dir,
            self.output_dir / "experiments",
            self.output_dir / "experiments" / "experiments",  # 兼容旧版重复嵌套目录。
        ]
        count = 0
        for root in roots:
            if not root.is_dir():
                continue
            for directory in sorted(root.iterdir()):
                config_path = directory / "config.json"
                if not directory.is_dir() or not config_path.is_file():
                    continue
                existing = self.tasks.get(directory.name)
                if existing and (
                    existing.status == TaskStatus.PENDING
                    or (existing.process is not None and existing.process.is_alive())
                ):
                    continue
                fingerprint = tuple(
                    (directory / name).stat().st_mtime_ns if (directory / name).exists() else 0
                    for name in (
                        "config.json",
                        "meta.json",
                        "notes.json",
                        "summary.json",
                        "status.json",
                    )
                )
                if (
                    changed_only
                    and self._file_versions.get(str(directory)) == fingerprint
                    and (existing is None or existing.status != TaskStatus.RUNNING)
                ):
                    continue
                try:
                    config = ExperimentConfig.model_validate_json(
                        config_path.read_text(encoding="utf-8")
                    )
                    meta_path = directory / "meta.json"
                    metadata = (
                        json.loads(meta_path.read_text(encoding="utf-8"))
                        if meta_path.exists()
                        else {}
                    )
                    status_path = directory / "status.json"
                    state = (
                        json.loads(status_path.read_text(encoding="utf-8"))
                        if status_path.exists()
                        else {}
                    )
                    raw_status = state.get("status", metadata.get("status", "failed"))
                    status = TaskStatus("queued" if raw_status == "pending" else raw_status)
                    if status == TaskStatus.PENDING:
                        from ..core.storage import ResultWriter

                        status = TaskStatus.CANCELLED
                        state["status"] = status.value
                        ResultWriter(directory)._write_json(status_path, state)
                    elif status == TaskStatus.RUNNING:
                        import psutil

                        if time.time() - state.get("heartbeat", 0) > 30 and not psutil.pid_exists(
                            int(state.get("pid", 0))
                        ):
                            status = TaskStatus.INTERRUPTED
                            state["error"] = "实验进程已退出，可整理已保存的部分结果或重新运行"
                    started = metadata.get("start_time", config_path.stat().st_mtime)
                    self.tasks[directory.name] = Task(
                        task_id=directory.name,
                        config=config,
                        status=status,
                        created_at=started,
                        started_at=started,
                        completed_at=started + metadata.get("elapsed_seconds", 0),
                        error=state.get("error"),
                        result_path=directory,
                        progress=state,
                    )
                    self._file_versions[str(directory)] = fingerprint
                    count += 1
                except (OSError, ValueError, TypeError) as exc:
                    logger.warning("跳过损坏的实验目录 %s：%s", directory, exc)
        if count or not changed_only:
            self._save_index()
        return count

    def _save_index(self) -> None:
        """原子写入任务索引。"""
        records = []
        for task in self.tasks.values():
            records.append(
                {
                    "task_id": task.task_id,
                    "config": task.config.model_dump(mode="json"),
                    "status": task.status.value,
                    "created_at": task.created_at,
                    "started_at": task.started_at,
                    "completed_at": task.completed_at,
                    "error": task.error,
                    "progress": task.progress,
                    "result_path": str(task.result_path) if task.result_path else None,
                }
            )
        with closing(sqlite3.connect(self._index_path)) as connection, connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS experiments (id TEXT PRIMARY KEY, record TEXT NOT NULL)"
            )
            connection.execute("DELETE FROM experiments")
            connection.executemany(
                "INSERT INTO experiments (id, record) VALUES (?, ?)",
                [(record["task_id"], json.dumps(record, ensure_ascii=False)) for record in records],
            )

    def create_task(self, config: ExperimentConfig, task_id: str | None = None) -> str:
        """创建任务。

        Args:
            config: 实验配置
            task_id: 场景集预创建的实验 ID；省略时自动生成

        Returns:
            任务 ID
        """
        task_id = task_id or str(uuid.uuid4())[:8]
        if Path(task_id).name != task_id or task_id in {".", ".."} or task_id in self.tasks:
            raise ValueError("任务 ID 无效或已经存在")

        # 结果路径
        result_path = self.output_dir / "experiments" / task_id

        task = Task(
            task_id=task_id,
            config=config,
            status=TaskStatus.PENDING,
            created_at=time.time(),
            result_path=result_path,
        )

        self.tasks[task_id] = task
        from ..core.storage import ResultWriter

        writer = ResultWriter(result_path)
        writer._write_json(result_path / "config.json", config.to_document())
        writer._write_json(
            result_path / "meta.json",
            {
                "status": task.status.value,
                "start_time": task.created_at,
            },
        )
        writer._write_json(result_path / "status.json", {"status": task.status.value})
        self._save_index()
        logger.info(f"任务已创建: {task_id}")

        return task_id

    async def run_task(self, task_id: str) -> None:
        """FIFO 锁保证同时仅运行一个实验，等待期间允许取消。"""
        async with self._run_lock:
            task = self.tasks.get(task_id)
            if task is not None and task.status == TaskStatus.PENDING:
                await self._execute_task(task_id)

    async def _execute_task(self, task_id: str) -> None:
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
        self._save_index()
        logger.info(f"任务开始: {task_id}")

        # 初始化进度
        total_points = 1
        if task.config.type == "sweep" and task.config.sweep:
            total_points = len(task.config.sweep.values)
        total_trials = total_points * task.config.trials
        task.progress = {
            "current_point": 0,
            "total_points": total_points,
            "current_trial": 0,
            "total_trials": task.config.trials,
            "completed_trials": 0,
            "percent": 0,
        }

        await self._notify_progress(task_id)

        from ..core.runner.job import run_job
        from ..core.storage.reader import read_result

        assert task.result_path is not None
        task.process = mp.get_context("spawn").Process(
            target=run_job,
            args=(task.config.model_dump(mode="json"), str(task.result_path.resolve())),
        )
        task.process.start()
        cancel_requested = None
        try:
            while task.process.is_alive():
                status_path = task.result_path / "status.json"
                if status_path.exists():
                    status = json.loads(status_path.read_text(encoding="utf-8"))
                    task.progress.update(status)
                    task.progress["current_trial"] = (
                        status.get("completed_trials", 0) % task.config.trials
                    )
                    await self._notify_progress(task_id)
                if task.status == TaskStatus.CANCELLED:
                    cancel_requested = cancel_requested or time.monotonic()
                    if time.monotonic() - cancel_requested > 10:
                        task.process.terminate()
                        break
                await asyncio.sleep(0.1)
            task.process.join(timeout=2)
            status_path = task.result_path / "status.json"
            status = (
                json.loads(status_path.read_text(encoding="utf-8")) if status_path.exists() else {}
            )
            if task.status != TaskStatus.CANCELLED:
                task.status = (
                    TaskStatus.COMPLETED
                    if status.get("status") == "completed"
                    else TaskStatus.FAILED
                )
            task.error = status.get("error")
            if (task.result_path / "results.npz").exists():
                task.result = read_result(task.result_path)
            task.completed_at = time.time()
            if task.status == TaskStatus.COMPLETED:
                task.progress.update(
                    completed_trials=total_trials,
                    total_trials=total_trials,
                    percent=100,
                    current_trial=task.config.trials,
                )
            self._save_index()
            await self._notify_progress(task_id)
        except Exception as exc:
            task.status = TaskStatus.FAILED
            task.error = str(exc)
            task.completed_at = time.time()
            self._save_index()
            await self._notify_progress(task_id)
        finally:
            if task.process.is_alive():
                task.process.terminate()
                task.process.join(timeout=2)

    async def _update_progress(
        self,
        task_id: str,
        completed_trials: int,
        total_trials: int,
        current_point: int,
        total_points: int,
    ) -> None:
        """更新任务进度并通知订阅者。"""
        task = self.tasks.get(task_id)
        if task is None:
            return
        point_trials = task.config.trials
        task.progress.update(
            {
                "current_point": current_point,
                "total_points": total_points,
                "current_trial": completed_trials - current_point * point_trials,
                "total_trials": point_trials,
                "completed_trials": completed_trials,
                "percent": int(completed_trials * 100 / total_trials) if total_trials else 100,
            }
        )
        await self._notify_progress(task_id)
        self._save_index()

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

    async def unsubscribe_progress(self, task_id: str, queue: asyncio.Queue) -> None:
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

    async def _notify_progress(self, task_id: str) -> None:
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

    @staticmethod
    def _progress_snapshot(task: Task) -> dict[str, Any]:
        """兼容旧取消记录的空百分比，进度来自实际完成次数。"""
        progress = dict(task.progress)
        if progress.get("percent") is None:
            total = progress.get("total_trials") or 0
            done = progress.get("completed_trials") or 0
            progress["percent"] = min(100, 100 * done / total) if total else 0
        return progress

    def _format_progress(self, task: Task) -> dict[str, Any]:
        """格式化进度消息。"""
        return {
            "task_id": task.task_id,
            "status": task.status.value,
            "progress": self._progress_snapshot(task),
            "elapsed_seconds": (time.time() - task.started_at if task.started_at else 0),
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

        status: dict[str, Any] = {
            "task_id": task.task_id,
            "status": task.status.value,
            "created_at": task.created_at,
            "name": task.config.name,
            "type": task.config.type,
            "config": task.config.model_dump(mode="json"),
        }

        if task.started_at:
            status["started_at"] = task.started_at

        if task.completed_at:
            status["completed_at"] = task.completed_at
            status["elapsed_seconds"] = task.completed_at - (task.started_at or task.created_at)

        if task.error:
            status["error"] = task.error

        if task.progress:
            status["progress"] = self._progress_snapshot(task)

        from .contracts import ExperimentNotes

        notes_path = task.result_path / "notes.json" if task.result_path else None
        notes = ExperimentNotes(tags=task.config.tags)
        if notes_path and notes_path.exists():
            notes = ExperimentNotes.model_validate_json(notes_path.read_text(encoding="utf-8"))
        status.update(notes=notes.notes, tags=notes.tags, starred=notes.starred)
        status["name"] = notes.display_name or task.config.name
        status["has_results"] = bool(
            task.result_path and (task.result_path / "results.npz").exists()
        )
        meta_path = task.result_path / "meta.json" if task.result_path else None
        if meta_path and meta_path.exists():
            metadata = json.loads(meta_path.read_text(encoding="utf-8"))
            status["mode"] = metadata.get("mode", "unknown")

        return status

    def list_tasks(self) -> list[dict[str, Any]]:
        """列出所有任务。

        Returns:
            任务列表
        """
        self.rebuild_index(changed_only=True)
        return [
            status
            for task_id in sorted(
                self.tasks.keys(),
                key=lambda tid: self.tasks[tid].created_at,
                reverse=True,
            )
            if (status := self.get_task_status(task_id)) is not None
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

        if task.result_path is not None:
            (task.result_path / "CANCEL").touch()
        task.status = TaskStatus.CANCELLED
        task.completed_at = time.time()
        self._save_index()
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
        from .routes.settings import CURRENT_WORKSPACE_PATH, _read_json

        current = _read_json(CURRENT_WORKSPACE_PATH, {})
        path = Path(current["path"]) if current.get("path") else None
        _task_manager = TaskManager(path if path is not None and path.is_dir() else None)
    return _task_manager
