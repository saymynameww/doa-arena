"""算法相关路由。"""

from fastapi import APIRouter, HTTPException

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


@router.get("/algorithms")
async def list_algorithms() -> dict:
    """列出可用算法及发现状态。"""
    return {
        "algorithms": _builtin_algorithms(),
        "failures": [],
        "sources": [{"name": "内置算法", "status": "ok"}],
    }


@router.post("/algorithms/refresh")
async def refresh_algorithms() -> dict:
    """刷新算法发现结果，返回可用算法和插件失败信息。"""
    return await list_algorithms()


@router.get("/algorithms/sources")
async def algorithm_sources() -> dict:
    """返回算法来源与发现状态。"""
    return {
        "sources": [{"name": "内置算法", "status": "ok", "count": len(_builtin_algorithms())}],
        "failures": [],
    }


@router.get("/algorithms/{algorithm_id}")
async def get_algorithm(algorithm_id: str) -> dict:
    """获取算法详情。"""
    for algo in _builtin_algorithms():
        if algo["id"] == algorithm_id:
            return algo
    raise HTTPException(status_code=404, detail="算法不存在")
