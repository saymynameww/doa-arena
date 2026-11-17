"""模型库管理；仅 JSON 列表在服务内读取，导入在隔离核心进程执行。"""

import asyncio
import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from arena_api import ModelMeta

from ..tasks import get_task_manager

router = APIRouter()


class ModelRecord(BaseModel):
    """可供模型选择器展示的元数据。"""

    path: str
    name: str
    algorithm_id: str
    metadata: dict[str, Any]


class ModelList(BaseModel):
    """当前工作目录下的模型列表和损坏项。"""

    models: list[ModelRecord]
    failures: list[str]
    generator_version: int


class ModelImportRequest(BaseModel):
    """本机模型包来源路径。"""

    path: str


class ModelInspection(BaseModel):
    """导入前的结构、哈希与插件检查结果。"""

    metadata: dict[str, Any]
    checks: list[str]
    warnings: list[str]


def workspace_path() -> Path:
    """与实验目录保持一致的当前工作目录。"""
    return get_task_manager().output_dir.resolve()


@router.get("/models", response_model=ModelList)
async def list_models() -> dict[str, Any]:
    """读取已导入模型的训练配置、版本及说明，不加载 torch。"""
    models = []
    failures = []
    for path in sorted((workspace_path() / "models").glob("*/model.json")):
        if path.parent.name.startswith("."):
            continue
        try:
            meta = ModelMeta.from_file(path)
            metadata = meta.model_dump(mode="json")
            imported = path.parent / "import.json"
            if imported.exists():
                metadata.update(json.loads(imported.read_text(encoding="utf-8")))
            models.append(
                {
                    "path": str(path.parent),
                    "name": meta.model_name,
                    "algorithm_id": meta.algorithm_id,
                    "metadata": metadata,
                }
            )
        except (OSError, ValueError) as exc:
            failures.append(f"{path.parent.name}：{exc}")
    from ...core.runner.core import GENERATOR_VERSION

    return {"models": models, "failures": failures, "generator_version": GENERATOR_VERSION}


@router.post("/models/inspect", response_model=ModelInspection)
async def inspect_model(request: ModelImportRequest) -> dict[str, Any]:
    """在确认导入之前展示校验结果。"""
    from ...core.operations import invoke
    from .algorithms import list_algorithms

    try:
        result = await asyncio.to_thread(invoke, "inspect_model", {"source": request.path})
        plugins = await list_algorithms()
        if any(p["id"] == result["metadata"]["algorithm_id"] for p in plugins["algorithms"]):
            result["checks"].append("对应算法插件已注册")
        else:
            result["warnings"].append("对应算法尚未注册；导入后需在设置中添加算法来源")
        return result
    except (OSError, ValueError) as exc:
        raise HTTPException(
            status_code=400, detail=f"模型包校验失败，请检查路径、文件权限与权重哈希：{exc}"
        ) from exc


@router.post("/models/import", response_model=ModelRecord)
async def import_model(request: ModelImportRequest) -> dict[str, Any]:
    """导入本地目录或 zip，不覆盖已经存在的模型包。"""
    from ...core.operations import invoke

    try:
        return await asyncio.to_thread(
            invoke, "import_model", {"source": request.path, "workspace": str(workspace_path())}
        )
    except (OSError, ValueError) as exc:
        raise HTTPException(
            status_code=400, detail=f"模型包校验失败，请检查路径、文件权限与权重哈希：{exc}"
        ) from exc
