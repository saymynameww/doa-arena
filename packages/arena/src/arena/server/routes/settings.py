"""设置和工作目录路由。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter

router = APIRouter()
SETTINGS_PATH = Path("arena_settings.json")
WORKSPACES_PATH = Path("workspaces.json")


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _write_json(path: Path, value: Any) -> None:
    temp_path = path.with_suffix(".tmp")
    temp_path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temp_path.replace(path)


@router.get("/settings")
async def get_settings() -> dict[str, Any]:
    """读取持久化设置。"""
    return _read_json(SETTINGS_PATH, {})


@router.put("/settings")
async def update_settings(settings: dict[str, Any]) -> dict[str, Any]:
    """更新持久化设置。"""
    _write_json(SETTINGS_PATH, settings)
    return settings


@router.get("/workspaces")
async def list_workspaces() -> dict[str, Any]:
    """列出工作目录。"""
    return {"workspaces": _read_json(WORKSPACES_PATH, [])}


@router.post("/workspaces")
async def add_workspace(workspace: dict[str, Any]) -> dict[str, Any]:
    """添加工作目录。"""
    workspaces = _read_json(WORKSPACES_PATH, [])
    if not isinstance(workspaces, list):
        workspaces = []
    workspaces.append(workspace)
    _write_json(WORKSPACES_PATH, workspaces)
    return workspace


@router.post("/workspaces/rebuild-index")
async def rebuild_workspace_index() -> dict[str, Any]:
    """返回索引重建结果。实验文件按目录读取，无需额外数据库。"""
    return {"rebuilt": True, "count": 0}
