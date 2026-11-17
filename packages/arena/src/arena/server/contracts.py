"""服务响应与可编辑信息模型，用于 OpenAPI 类型生成。"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from ..core.config import ExperimentConfig


class ExperimentNotes(BaseModel):
    """与实验计算配置分离的用户备注。"""

    schema_version: int = 1
    display_name: str | None = None
    notes: str = ""
    tags: list[str] = Field(default_factory=list)
    starred: bool = False
    updated_at: str = Field(default_factory=lambda: datetime.now().astimezone().isoformat())


class TaskProgress(BaseModel):
    """任务进度快照。"""

    current_point: int = 0
    total_points: int = 1
    current_trial: int = 0
    total_trials: int = 0
    completed_trials: int = 0
    percent: float = 0
    eta_seconds: float | None = None


class TaskResponse(BaseModel):
    """任务与历史列表共享响应。"""

    task_id: str
    status: Literal["queued", "running", "completed", "failed", "cancelled", "interrupted"]
    created_at: float
    started_at: float | None = None
    completed_at: float | None = None
    elapsed_seconds: float | None = None
    error: str | None = None
    name: str = ""
    type: Literal["single", "monte_carlo", "sweep"] = "single"
    config: ExperimentConfig
    progress: TaskProgress | None = None
    mode: str = "unknown"
    has_results: bool = False
    notes: str = ""
    tags: list[str] = Field(default_factory=list)
    starred: bool = False


class TaskList(BaseModel):
    """历史列表响应。"""

    tasks: list[TaskResponse]


class ResultFiles(BaseModel):
    """结果文件清单。"""

    task_id: str
    result_path: str
    files: list[str]


class ChartData(BaseModel):
    """核心生成的 Plotly 数据。"""

    title: str
    data: list[dict[str, Any]]
    layout: dict[str, Any]


class ChartList(BaseModel):
    """可用图表清单。"""

    charts: list[ChartData]


class ResultDetails(BaseModel):
    """核心生成的逐点指标与复现元信息。"""

    rows: list[dict[str, Any]]
    columns: list[dict[str, str]]
    metadata: dict[str, Any]
    error_groups: list[dict[str, Any]] = Field(default_factory=list)


class Template(BaseModel):
    """可复用实验模板。"""

    id: str
    name: str
    description: str = ""
    type: str = "single"
    algorithms: list[str] = Field(default_factory=list)
    createdAt: str = ""
    level: str = "工作目录"
    kind: Literal["scenario", "experiment"] = "experiment"
    config: ExperimentConfig = Field(default_factory=lambda: ExperimentConfig.model_validate({}))


class TemplateList(BaseModel):
    """模板列表。"""

    templates: list[Template]


class ValidationIssue(BaseModel):
    """配置校验的可定位问题。"""

    level: Literal["error", "warning"]
    message: str
    algorithm: str | None = None
    point: int | None = None
    param: str | None = None
    component: str | None = None


class ValidationResult(BaseModel):
    """草稿校验响应。"""

    valid: bool
    issues: list[ValidationIssue]
    config: dict[str, Any] | None = None


class ParamSchema(BaseModel):
    """插件字段的 JSON Schema，保留所有扩展关键字。"""

    model_config = {"extra": "allow"}
    type: str = "object"
    default: Any = None
    min: float | None = None
    max: float | None = None
    enum: list[str] | None = None
    description: str = ""
    title: str = ""
    label: str = Field(default="", alias="x-label")


class PluginInfo(BaseModel):
    """四类插件的统一发现元信息。"""

    kind: str
    id: str
    name: str
    version: str
    type: Literal["builtin", "external"]
    description: str
    category: str
    params: dict[str, ParamSchema]
    params_schema: dict[str, Any] = Field(alias="schema")
    capabilities: dict[str, Any]
    origin: dict[str, Any] | None
    defaults: dict[str, Any]


class PluginList(BaseModel):
    """插件注册和失败隔离结果。"""

    algorithms: list[PluginInfo]
    arrays: list[PluginInfo]
    impairments: list[PluginInfo]
    metrics: list[PluginInfo]
    failures: list[dict[str, Any]]
    sources: list[dict[str, Any]]


class ScenarioPreview(BaseModel):
    """核心计算的可视化摘要。"""

    elements: int
    angles: list[float]
    physical_spacing_cm: float | None
    ranges: list[dict[str, float]] = Field(default_factory=list)
    faulty_elements: list[int] = Field(default_factory=list)
    positions: list[list[float]] = Field(default_factory=list)
