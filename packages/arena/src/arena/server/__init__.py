"""Web 服务模块。

FastAPI 后端，提供 REST API 和实时进度推送。
"""

from .app import create_app

__all__ = ["create_app"]
