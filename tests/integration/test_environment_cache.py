"""环境缓存、并发刷新和服务生命周期回归。"""

import asyncio
import threading
import time

from fastapi.testclient import TestClient

from arena.server.app import create_app


def wait_ready(client):
    for _ in range(100):
        result = client.get("/api/settings/environment").json()
        if result["status"] != "detecting":
            return result
        time.sleep(0.01)
    raise AssertionError("环境检测没有完成")


def test_startup_and_reads_do_not_wait_or_repeat_probe(monkeypatch):
    from arena.server import environment

    release = threading.Event()
    calls = []

    async def probe():
        calls.append(1)
        while not release.is_set():
            await asyncio.sleep(0.01)
        return {"cuda_available": True, "GPU": "test-device"}

    monkeypatch.setattr(environment, "probe_environment", probe)
    with TestClient(create_app()) as client:
        # 探测尚未结束，服务必须已启动，Schema 和缓存请求都必须能返回。
        assert client.get("/api/health").status_code == 200
        assert client.get("/api/schema/experiment").status_code == 200
        for _ in range(5):
            result = client.get("/api/settings/environment").json()
            assert result["status"] == "detecting"
            assert result["cuda_available"] is None
            assert client.post("/api/settings/environment/refresh").json()["status"] == "detecting"
        assert len(calls) == 1
        release.set()
        ready = wait_ready(client)
        assert ready["cuda_available"] is True
        for _ in range(5):
            assert client.get("/api/settings/environment").json() == ready
        assert len(calls) == 1
        client.post("/api/settings/environment/refresh")
        assert wait_ready(client)["status"] == "available"
        assert len(calls) == 2
    # 新服务不沿用旧服务结果。
    with TestClient(create_app()) as client:
        assert wait_ready(client)["status"] == "available"
        assert len(calls) == 3


def test_failed_probe_is_cached_and_can_be_retried(monkeypatch):
    from arena.server import environment

    calls = []

    async def probe():
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("驱动探测失败")
        return {"cuda_available": False, "GPU": "不可用"}

    monkeypatch.setattr(environment, "probe_environment", probe)
    with TestClient(create_app()) as client:
        failed = wait_ready(client)
        assert failed["status"] == "error"
        assert failed["cuda_available"] is None
        assert "驱动探测失败" in failed["error"]
        assert client.get("/api/settings/environment").json() == failed
        assert len(calls) == 1
        client.post("/api/settings/environment/refresh")
        ready = wait_ready(client)
        assert ready["status"] == "unavailable"
        assert ready["cuda_available"] is False


def test_shutdown_cancels_pending_probe(monkeypatch):
    from arena.server import environment

    closed = threading.Event()

    async def probe():
        try:
            await asyncio.sleep(3600)
        finally:
            closed.set()

    monkeypatch.setattr(environment, "probe_environment", probe)
    with TestClient(create_app()) as client:
        assert client.get("/api/settings/environment").json()["status"] == "detecting"
    assert closed.is_set()


def test_probe_cancellation_kills_child(monkeypatch):
    from arena.server import environment

    class Process:
        returncode = None
        killed = False

        async def communicate(self, payload):
            raise asyncio.CancelledError

        def kill(self):
            self.killed = True

        async def wait(self):
            self.returncode = -1

    process = Process()

    async def spawn(*args, **kwargs):
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)

    async def run():
        try:
            await environment.probe_environment()
        except asyncio.CancelledError:
            pass
        else:
            raise AssertionError("取消必须传播")

    asyncio.run(run())
    assert process.killed
    assert process.returncode == -1
