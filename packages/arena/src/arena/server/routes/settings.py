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
    records = []
    actual = get_task_manager().output_dir.resolve()
    if not any(Path(w.get("path", "")).resolve() == actual for w in workspaces):
        workspaces.append({"path": str(actual), "name": (current or {}).get("name", actual.name)})
    for workspace in sorted(workspaces, key=lambda w: Path(w.get("path", "")).resolve() != actual):
        path = Path(workspace.get("path", ""))
        index = path / ".arena_index.sqlite"
        records.append(
            {
                **workspace,
                "exists": path.is_dir(),
                "experiments": len(list((path / "experiments").glob("*/config.json"))),
                "indexed_at": index.stat().st_mtime if index.exists() else None,
            }
        )
    return {"workspaces": records, "current": current}


@router.post("/workspaces")
async def add_workspace(workspace: dict[str, Any]) -> dict[str, Any]:
    """添加工作目录。"""
    workspaces = _read_json(WORKSPACES_PATH, [])
    if not isinstance(workspaces, list):
        workspaces = []
    path_value = str(workspace.get("path", "")).strip()
    if not path_value:
        raise HTTPException(status_code=400, detail="请输入工作目录路径")
    path = Path(path_value).expanduser().resolve()
    workspace = {"name": workspace.get("name") or path.name, "path": str(path)}
    if any(Path(w.get("path", "")).resolve() == path for w in workspaces):
        raise HTTPException(status_code=409, detail="该工作目录已在列表中")
    workspaces.append(workspace)
    _write_json(WORKSPACES_PATH, workspaces)
    return workspace


@router.put("/workspaces/current")
async def select_workspace(workspace: dict[str, Any]) -> dict[str, Any]:
    """切换当前工作目录，并让新任务写入该目录。"""
    path_value = workspace.get("path") or workspace.get("name")
    if not isinstance(path_value, str) or not path_value.strip():
        raise HTTPException(status_code=400, detail="工作目录必须提供 path 或 name")
    manager = get_task_manager()
    if any(task.status.value in {"queued", "running"} for task in manager.tasks.values()):
        raise HTTPException(status_code=409, detail="请等待当前任务完成或取消后再切换工作目录")
    from ...core.facade import Workspace

    initialized = Workspace(path_value)
    selected = {**workspace, "path": str(initialized.path)}
    _write_json(CURRENT_WORKSPACE_PATH, selected)
    manager = get_task_manager()
    manager.switch_output_dir(initialized.path)
    return selected


@router.get("/workspaces/current")
async def get_current_workspace() -> dict[str, Any]:
    """读取当前工作目录。"""
    selected = _read_json(CURRENT_WORKSPACE_PATH, {})
    actual = get_task_manager().output_dir.resolve()
    if selected.get("path") and Path(selected["path"]).resolve() == actual:
        return selected
    return {"path": str(actual), "name": actual.name}


@router.post("/workspaces/rebuild-index")
async def rebuild_workspace_index() -> dict[str, Any]:
    """从实验文件恢复索引，包含脚本模式创建的实验。"""
    count = get_task_manager().rebuild_index()
    return {"rebuilt": True, "count": count}


@router.delete("/workspaces")
async def remove_workspace(path: str) -> dict[str, bool]:
    """仅移除登记，不删除实验文件或目录。"""
    target = Path(path).resolve()
    if target == get_task_manager().output_dir.resolve():
        raise HTTPException(status_code=409, detail="请先切换到其他工作目录")
    records = _read_json(WORKSPACES_PATH, [])
    _write_json(
        WORKSPACES_PATH, [w for w in records if Path(w.get("path", "")).resolve() != target]
    )
    return {"removed": True}


@router.get("/settings/environment")
async def get_environment() -> dict[str, Any]:
    """在隔离进程探测运行环境，Web 服务不加载 torch。"""
    import asyncio

    from ...core.operations import invoke

    return await asyncio.to_thread(invoke, "environment", {})
