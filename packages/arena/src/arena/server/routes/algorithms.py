"""算法相关路由。"""

from fastapi import APIRouter, HTTPException

router = APIRouter()


@router.get("/algorithms")
async def list_algorithms():
    """列出可用算法。

    Returns:
        算法列表
    """
    # 内置算法
    algorithms = [
        {
            "id": "cbf",
            "name": "CBF",
            "description": "常规波束形成",
            "type": "spectral",
            "params": {
                "grid_step": {
                    "type": "number",
                    "default": 0.1,
                    "min": 0.01,
                    "max": 1.0,
                    "description": "网格步长（度）",
                },
            },
        },
        {
            "id": "mvdr",
            "name": "MVDR",
            "description": "最小方差无失真响应",
            "type": "spectral",
            "params": {
                "grid_step": {
                    "type": "number",
                    "default": 0.1,
                    "min": 0.01,
                    "max": 1.0,
                },
            },
        },
        {
            "id": "music",
            "name": "MUSIC",
            "description": "多重信号分类",
            "type": "subspace",
            "params": {
                "grid_step": {
                    "type": "number",
                    "default": 0.1,
                },
                "smoothing": {
                    "type": "string",
                    "default": "none",
                    "enum": ["none", "forward", "fb"],
                    "description": "空间平滑",
                },
                "subarray_size": {
                    "type": "integer",
                    "default": None,
                    "description": "子阵大小（空间平滑时必填）",
                },
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
                "subarray_size": {
                    "type": "integer",
                    "default": None,
                },
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
                "subarray_size": {
                    "type": "integer",
                    "default": None,
                },
            },
        },
    ]

    return {"algorithms": algorithms}


@router.get("/algorithms/{algorithm_id}")
async def get_algorithm(algorithm_id: str):
    """获取算法详情。

    Args:
        algorithm_id: 算法 ID

    Returns:
        算法详情
    """
    # 简化：从列表中查找
    algorithms = (await list_algorithms())["algorithms"]

    for algo in algorithms:
        if algo["id"] == algorithm_id:
            return algo

    raise HTTPException(status_code=404, detail="算法不存在")
