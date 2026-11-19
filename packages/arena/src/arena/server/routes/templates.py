"""实验模板路由。"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

from ..contracts import Template, TemplateList
from .settings import _write_json

router = APIRouter()
TEMPLATES_DIR = Path("templates")


def _workspace_templates() -> Path:
    from ..tasks import get_task_manager

    # 可注入路径用于隔离测试；实际用户模板随工作目录保存。
    if TEMPLATES_DIR != Path("templates"):
        return TEMPLATES_DIR
    return get_task_manager().output_dir / "templates"


def _template_path(identifier: str) -> Path:
    if not re.fullmatch(r"[a-zA-Z0-9_-]{1,100}", identifier):
        raise HTTPException(status_code=400, detail="模板 ID 只能包含字母、数字、下划线或短横线")
    local = _workspace_templates() / f"{identifier}.json"
    if local.exists():
        return local
    legacy = TEMPLATES_DIR / f"{identifier}.json"
    return legacy if legacy.exists() else local


def _ensure_templates() -> None:
    """初始化默认模板文件。"""
    TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
    defaults = [
        {
            "id": "default-scenario",
            "name": "默认场景",
            "description": "使用当前核心库的默认阵列、信源及误差配置；保留已有算法和运行设置。",
            "kind": "scenario",
            "level": "内置",
            "config": {},
        },
        {
            "id": "standard-comparison",
            "name": "标准 DOA 对比",
            "description": "MUSIC、ESPRIT、Root-MUSIC 三算法对比",
            "type": "monte_carlo",
            "algorithms": ["music", "esprit", "root_music"],
            "createdAt": "2026-11-10",
            "level": "内置",
            "config": {"type": "monte_carlo", "trials": 50},
        },
        {
            "id": "snr-sweep",
            "name": "SNR 扫描实验",
            "description": "扫描 SNR -10 到 20 dB，步长 5 dB",
            "type": "sweep",
            "algorithms": ["music", "esprit"],
            "createdAt": "2026-11-12",
            "level": "内置",
            "config": {
                "type": "sweep",
                "trials": 50,
                "sweep": {"path": "scenario.sources.snr_db", "values": [-10, -5, 0, 5, 10, 15, 20]},
            },
        },
    ]
    for template in defaults:
        path = TEMPLATES_DIR / f"{template['id']}.json"
        if not path.exists():
            _write_json(path, template)
        else:
            try:
                existing = json.loads(path.read_text(encoding="utf-8"))
                if existing.get("level") != "内置":
                    existing["level"] = "内置"
                    _write_json(path, existing)
            except (OSError, json.JSONDecodeError):
                _write_json(path, template)


def _read_templates() -> list[dict[str, Any]]:
    _ensure_templates()
    templates = []
    paths = {*TEMPLATES_DIR.glob("*.json"), *_workspace_templates().glob("*.json")}
    for path in sorted(paths):
        template = json.loads(path.read_text(encoding="utf-8"))
        config = template.get("config", {})
        if template.get("level") != "内置" and config.get("algorithms"):
            # 旧模板可能没有版本号；仅在读取存量文件时按旧语义解释，不改写原文件。
            from ...core.config import ExperimentConfig

            config = {"schema_version": 1, **config}
            template["config"] = ExperimentConfig.model_validate(config).model_dump(mode="json")
        templates.append(template)
    return templates


@router.get("/templates", response_model=TemplateList)
async def list_templates() -> dict[str, Any]:
    """列出持久化模板。"""
    return {"templates": _read_templates()}


@router.post("/templates", response_model=Template)
async def create_template(template: dict[str, Any]) -> dict[str, Any]:
    """创建模板。"""
    _ensure_templates()
    template = dict(template)
    template.setdefault("id", uuid.uuid4().hex[:8])
    template.setdefault("level", "工作目录")
    path = _template_path(template["id"])
    if path.exists():
        raise HTTPException(
            status_code=409, detail="模板 ID 已存在，请使用新 ID 或编辑工作目录模板"
        )
    template["level"] = "工作目录"
    template["createdAt"] = datetime.now().astimezone().isoformat()
    path.parent.mkdir(parents=True, exist_ok=True)
    _write_json(path, template)
    return template


@router.delete("/templates/{template_id}")
async def delete_template(template_id: str) -> dict[str, str]:
    """删除模板。"""
    path = _template_path(template_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="模板不存在")
    current = json.loads(path.read_text(encoding="utf-8"))
    if current.get("level") == "内置":
        raise HTTPException(status_code=403, detail="内置模板不能直接删除，请先复制到工作目录")
    trash_dir = path.parent / ".trash"
    trash_dir.mkdir(exist_ok=True)
    path.replace(trash_dir / (uuid.uuid4().hex[:8] + "_" + path.name))
    return {"message": "模板已删除"}


@router.put("/templates/{template_id}", response_model=Template)
async def update_template(template_id: str, template: dict[str, Any]) -> dict[str, Any]:
    """更新工作目录模板。"""
    path = _template_path(template_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="模板不存在")
    current = json.loads(path.read_text(encoding="utf-8"))
    if current.get("level") == "内置":
        raise HTTPException(status_code=403, detail="内置模板不能直接修改，请先复制到工作目录")
    updated = dict(template)
    updated["id"] = template_id
    updated["createdAt"] = datetime.now().astimezone().isoformat()
    _write_json(path, updated)
    return updated
