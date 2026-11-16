"""算法相关路由。"""

from fastapi import APIRouter, HTTPException

from ..contracts import PluginInfo, PluginList

router = APIRouter()


def _builtin_algorithms() -> list[dict]:
    """返回内置算法清单。"""
    from ...core.algorithms import CBF, ESPRIT, MUSIC, MVDR, RootMUSIC

    return [
        {
            "id": cls.id,
            "name": cls.name,
            "description": (cls.__doc__ or "").strip(),
            "type": "builtin",
            "schema": cls.Params.model_json_schema(),
            "params": cls.Params.model_json_schema().get("properties", {}),
        }
        for cls in (CBF, MVDR, MUSIC, RootMUSIC, ESPRIT)
    ]


def _discover() -> dict:
    """只在子进程导入外部代码。"""
    from pathlib import Path

    from ...core.plugins import probe
    from .settings import CURRENT_WORKSPACE_PATH, SETTINGS_PATH, _read_json

    settings = _read_json(SETTINGS_PATH, {})
    current = _read_json(CURRENT_WORKSPACE_PATH, {})
    workspace = _read_json(Path(current.get("path", ".")) / "arena_workspace.json", {})
    sources = settings.get("algorithm_sources", []) + workspace.get("algorithm_sources", [])
    if not sources:
        from ...core.plugins import discover

        return discover([])
    data = probe(sources)
    data["sources"] = [
        {"name": s.get("name", s.get("value", "")), "status": "ok", **s} for s in sources
    ]
    return data


@router.get("/algorithms", response_model=PluginList)
async def list_algorithms() -> dict:
    """列出真实发现结果及失败入口。"""
    return _discover()


@router.post("/algorithms/refresh", response_model=PluginList)
async def refresh_algorithms() -> dict:
    """重新扫描入口，探测进程每次重建，不复用旧模块。"""
    return _discover()


@router.get("/algorithms/sources", response_model=PluginList)
async def algorithm_sources() -> dict:
    """返回全局和工作目录来源。"""
    return _discover()


@router.get("/algorithms/{algorithm_id:path}", response_model=PluginInfo)
async def get_algorithm(algorithm_id: str) -> dict:
    """查询含命名空间的插件 id。"""
    for algo in _discover()["algorithms"]:
        if algo["id"] == algorithm_id:
            return algo
    raise HTTPException(status_code=404, detail="算法不存在，请刷新算法来源")
