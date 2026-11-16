"""算法相关路由。"""

from fastapi import APIRouter, HTTPException

router = APIRouter()


def _builtin_algorithms() -> list[dict]:
    """返回内置算法清单。"""
    return [
        {
            "id": "cbf",
            "name": "CBF",
            "description": "常规波束形成",
            "type": "spectral",
            "params": {"grid_step": {"type": "number", "default": 0.1, "min": 0.01, "max": 1.0}},
        },
        {
            "id": "mvdr",
            "name": "MVDR",
            "description": "最小方差无失真响应",
            "type": "spectral",
            "params": {"grid_step": {"type": "number", "default": 0.1, "min": 0.01, "max": 1.0}},
        },
        {
            "id": "music",
            "name": "MUSIC",
            "description": "多重信号分类",
            "type": "subspace",
            "params": {
                "grid_step": {"type": "number", "default": 0.1},
                "smoothing": {
                    "type": "string",
                    "default": "none",
                    "enum": ["none", "forward", "fb"],
                },
                "subarray_size": {"type": "integer", "default": None},
            },
        },
        {
            "id": "root_music",
            "name": "Root-MUSIC",
            "description": "求根 MUSIC",
            "type": "subspace",
            "params": {
                "smoothing": {
                    "type": "string",
                    "default": "none",
                    "enum": ["none", "forward", "fb"],
                },
                "subarray_size": {"type": "integer", "default": None},
            },
        },
        {
            "id": "esprit",
            "name": "ESPRIT",
            "description": "旋转不变子空间",
            "type": "subspace",
            "params": {
                "smoothing": {
                    "type": "string",
                    "default": "none",
                    "enum": ["none", "forward", "fb"],
                },
                "subarray_size": {"type": "integer", "default": None},
            },
        },
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
