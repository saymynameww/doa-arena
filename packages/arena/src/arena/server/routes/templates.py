"""实验模板路由。"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

router = APIRouter()
TEMPLATES_DIR = Path("templates")


def _ensure_templates() -> None:
    """初始化默认模板文件。"""
    TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
    defaults = [
        {
            "id": "standard-comparison",
            "name": "标准 DOA 对比",
            "description": "MUSIC、ESPRIT、Root-MUSIC 三算法对比",
            "type": "monte_carlo",
            "algorithms": ["music", "esprit", "root_music"],
            "createdAt": "2026-11-10",
            "config": {"type": "monte_carlo", "trials": 50},
        },
        {
            "id": "snr-sweep",
            "name": "SNR 扫描实验",
            "description": "扫描 SNR -10 到 20 dB，步长 5 dB",
            "type": "sweep",
            "algorithms": ["music", "esprit"],
            "createdAt": "2026-11-12",
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
            path.write_text(json.dumps(template, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_templates() -> list[dict[str, Any]]:
    _ensure_templates()
    templates = []
    for path in sorted(TEMPLATES_DIR.glob("*.json")):
        templates.append(json.loads(path.read_text(encoding="utf-8")))
    return templates


@router.get("/templates")
async def list_templates() -> dict[str, Any]:
    """列出持久化模板。"""
    return {"templates": _read_templates()}


@router.post("/templates")
async def create_template(template: dict[str, Any]) -> dict[str, Any]:
    """创建模板。"""
    _ensure_templates()
    template = dict(template)
    template.setdefault("id", uuid.uuid4().hex[:8])
    (TEMPLATES_DIR / f"{template['id']}.json").write_text(
        json.dumps(template, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return template


@router.delete("/templates/{template_id}")
async def delete_template(template_id: str) -> dict[str, str]:
    """删除模板。"""
    path = TEMPLATES_DIR / f"{template_id}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="模板不存在")
    trash_dir = TEMPLATES_DIR / ".trash"
    trash_dir.mkdir(exist_ok=True)
    path.replace(trash_dir / path.name)
    return {"message": "模板已删除"}


@router.put("/templates/{template_id}")
async def update_template(template_id: str, template: dict[str, Any]) -> dict[str, Any]:
    """更新工作目录模板。"""
    path = TEMPLATES_DIR / f"{template_id}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="模板不存在")
    updated = dict(template)
    updated["id"] = template_id
    path.write_text(json.dumps(updated, ensure_ascii=False, indent=2), encoding="utf-8")
    return updated
