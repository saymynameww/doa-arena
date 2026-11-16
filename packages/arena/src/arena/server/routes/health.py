"""健康检查路由。"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health_check() -> dict[str, str]:
    """健康检查。

    Returns:
        健康状态
    """
    return {"status": "ok", "service": "arena-web"}
