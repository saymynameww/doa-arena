"""设置和工作目录路由。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

from ..tasks import get_task_manager

router = APIRouter()
SETTINGS_PATH = Path("arena_settings.json")
WORKSPACES_PATH = Path("workspaces.json")
CURRENT_WORKSPACE_PATH = Path("current_workspace.json")


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
    workspaces = _read_json(WORKSPACES_PATH, [])
    current = _read_json(CURRENT_WORKSPACE_PATH, None)
    return {"workspaces": workspaces, "current": current}


@router.post("/workspaces")
async def add_workspace(workspace: dict[str, Any]) -> dict[str, Any]:
    """添加工作目录。"""
    workspaces = _read_json(WORKSPACES_PATH, [])
    if not isinstance(workspaces, list):
        workspaces = []
    workspaces.append(workspace)
    _write_json(WORKSPACES_PATH, workspaces)
    return workspace


@router.put("/workspaces/current")
async def select_workspace(workspace: dict[str, Any]) -> dict[str, Any]:
    """切换当前工作目录，并让新任务写入该目录。"""
    path_value = workspace.get("path") or workspace.get("name")
    if not isinstance(path_value, str) or not path_value.strip():
        raise HTTPException(status_code=400, detail="工作目录必须提供 path 或 name")
    selected = {**workspace, "path": path_value}
    _write_json(CURRENT_WORKSPACE_PATH, selected)
    manager = get_task_manager()
    manager.switch_output_dir(Path(path_value))
    return selected


@router.get("/workspaces/current")
async def get_current_workspace() -> dict[str, Any]:
    """读取当前工作目录。"""
    return _read_json(CURRENT_WORKSPACE_PATH, {})


@router.post("/workspaces/rebuild-index")
async def rebuild_workspace_index() -> dict[str, Any]:
    """从实验文件恢复索引，包含脚本模式创建的实验。"""
    count = get_task_manager().rebuild_index()
    return {"rebuilt": True, "count": count}
