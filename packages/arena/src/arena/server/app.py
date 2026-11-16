"""FastAPI 应用主模块。"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes import algorithms, experiments, health, leaderboard, schema, settings, templates

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """应用生命周期管理。"""
    # 启动
    logger.info("Arena Web 服务启动")
    yield
    # 关闭
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

    return app
