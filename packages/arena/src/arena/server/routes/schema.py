"""配置 Schema 路由。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from ...core.config import ExperimentConfig
from .algorithms import list_algorithms

router = APIRouter()


@router.get("/schema/experiment")
async def experiment_schema() -> dict[str, Any]:
    """返回前端生成实验配置表单所需的完整 Schema。"""
    schema = ExperimentConfig.model_json_schema()
    algorithms = (await list_algorithms())["algorithms"]
    schema["x-algorithms"] = algorithms
    schema["x-sweep-paths"] = [
        {
            "path": "scenario.sources.snr_db",
            "label": "SNR",
            "unit": "dB",
        },
        {
            "path": "scenario.snapshots",
            "label": "快拍数",
            "unit": "",
        },
        {
            "path": "scenario.sources.K",
            "label": "信源数 K",
            "unit": "",
        },
    ]
    return schema
