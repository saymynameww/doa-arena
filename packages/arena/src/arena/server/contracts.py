"""服务响应与可编辑信息模型，用于 OpenAPI 类型生成。"""

from datetime import datetime

from pydantic import BaseModel, Field


class ExperimentNotes(BaseModel):
    """与实验计算配置分离的用户备注。"""

    schema_version: int = 1
    display_name: str | None = None
    notes: str = ""
    tags: list[str] = Field(default_factory=list)
    starred: bool = False
    updated_at: str = Field(default_factory=lambda: datetime.now().astimezone().isoformat())
