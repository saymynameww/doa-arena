"""FastAPI 应用主模块。"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from .environment import EnvironmentMonitor
from .routes import (
    algorithms,
    experiments,
    health,
    leaderboard,
    models,
    schema,
    settings,
    templates,
)

logger = logging.getLogger(__name__)
STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """应用生命周期管理。"""
    # 启动
    logger.info("Arena Web 服务启动")
    app.state.environment.refresh()
    try:
        yield
    finally:
        await app.state.environment.close()
        logger.info("Arena Web 服务关闭")


def create_app() -> FastAPI:
    """创建 FastAPI 应用。

    Returns:
        FastAPI 应用实例
    """
    app = FastAPI(
        title="DOA 估计算法竞技场",
        description="DOA Estimation Arena - Web API",
        version="0.4.0",
        lifespan=lifespan,
    )
    app.state.environment = EnvironmentMonitor()

    # CORS（开发模式）
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],  # 前端开发服务器
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 注册路由
    app.include_router(health.router, prefix="/api", tags=["health"])
    app.include_router(experiments.router, prefix="/api", tags=["experiments"])
    app.include_router(algorithms.router, prefix="/api", tags=["algorithms"])
    app.include_router(schema.router, prefix="/api", tags=["schema"])
    app.include_router(templates.router, prefix="/api", tags=["templates"])
    app.include_router(settings.router, prefix="/api", tags=["settings"])
    app.include_router(leaderboard.router, prefix="/api", tags=["leaderboard"])
    app.include_router(models.router, prefix="/api", tags=["models"])

    from ..core.config import ExperimentConfig

    document = app.openapi()
    configuration = ExperimentConfig.model_json_schema(ref_template="#/components/schemas/{model}")
    document["components"]["schemas"].update(configuration.pop("$defs", {}))
    document["components"]["schemas"]["ExperimentConfig"] = configuration
    document["paths"]["/api/experiments/run"]["post"]["requestBody"]["content"]["application/json"][
        "schema"
    ] = {"$ref": "#/components/schemas/ExperimentConfig"}

    @app.get("/{path:path}", include_in_schema=False)
    async def frontend(path: str) -> FileResponse:
        """提供安装包内的前端及 SPA 路由，缺失 API 和资源保持 404。"""
        root = STATIC_DIR.resolve()
        target = (root / path).resolve()
        if not target.is_relative_to(root) or path == "api" or path.startswith("api/"):
            raise HTTPException(404, "路径不存在")
        if target.is_file():
            return FileResponse(target)
        if Path(path).suffix or path.startswith("assets/"):
            raise HTTPException(404, "资源不存在，请刷新页面")
        index = root / "index.html"
        if not index.is_file():
            raise HTTPException(503, "尚未构建前端，请运行 python scripts/build_release.py")
        return FileResponse(index)

    return app
