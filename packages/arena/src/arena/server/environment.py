"""服务生命周期内共享环境探测结果，探测进程不阻塞请求。"""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime, timezone
from typing import Any

from .contracts import EnvironmentStatus


async def probe_environment() -> dict[str, Any]:
    """隔离导入 torch，超时或服务关闭时回收子进程。"""
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "arena.core.operations",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        payload = json.dumps({"operation": "environment", "payload": {}}).encode("utf-8")
        stdout, stderr = await asyncio.wait_for(process.communicate(payload), timeout=120)
        if process.returncode:
            raise RuntimeError(f"环境检测失败：{stderr.decode('utf-8', errors='replace')[-1000:]}")
        result = json.loads(stdout)
        if "error" in result:
            raise RuntimeError(result["error"])
        return dict(result)
    finally:
        if process.returncode is None:
            process.kill()
            await process.wait()


class EnvironmentMonitor:
    """单个服务共享一次探测；显式刷新时合并同时到达的请求。"""

    def __init__(self) -> None:
        self.snapshot = EnvironmentStatus()
        self.task: asyncio.Task[None] | None = None

    def refresh(self) -> EnvironmentStatus:
        """启动后台检测并立即返回，已有检测未完成时复用。"""
        if self.task is None or self.task.done():
            self.snapshot = EnvironmentStatus()
            self.task = asyncio.create_task(self._detect())
        return self.snapshot

    async def _detect(self) -> None:
        try:
            details = await probe_environment()
            available = details.get("cuda_available") is True
            self.snapshot = EnvironmentStatus(
                status="available" if available else "unavailable",
                cuda_available=available,
                details=details,
                checked_at=datetime.now(timezone.utc).isoformat(),
            )
        except Exception as exc:
            self.snapshot = EnvironmentStatus(
                status="error",
                error=f"环境检测失败，请重新检测；安装依赖或切换环境后请重启服务。{exc}",
                checked_at=datetime.now(timezone.utc).isoformat(),
            )

    async def close(self) -> None:
        """服务关闭时取消检测并等待子进程回收。"""
        if self.task is not None:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
