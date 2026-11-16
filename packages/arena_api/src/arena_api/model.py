"""模型包元数据的只读视图；读取不会导入 torch 或加载权重。"""

from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .grid import AngleGrid


class ModelOutput(BaseModel):
    """模型输出声明。"""

    model_config = ConfigDict(frozen=True, extra="allow")
    type: str
    grid: AngleGrid | None = None

    def __getitem__(self, key: str) -> Any:
        """兼容接口规范示例中的字典访问写法。"""
        return self.model_dump(mode="json")[key]


class ModelMeta(BaseModel):
    """数据格式 6.2 定义的模型元数据。"""

    model_config = ConfigDict(frozen=True, extra="allow")
    schema_version: Literal[1] = 1
    model_name: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    description: str = ""
    algorithm_id: str
    api_version: Literal[1] = 1
    array: dict[str, Any]
    input: str
    output: ModelOutput
    hparams: dict[str, Any] = Field(default_factory=dict)
    weights: dict[str, str]
    trained_on: dict[str, Any] = Field(default_factory=lambda: {"source": "external"})
    training: dict[str, Any] = Field(default_factory=dict)
    created_at: str | None = None
    path: Path = Field(default=Path("."), exclude=True)

    @model_validator(mode="after")
    def check_package(self) -> ModelMeta:
        """固定权重文件名和安全格式，阻止读取模型目录以外文件。"""
        if self.weights.get("file") != "model.pt" or self.weights.get("format") != "state_dict":
            raise ValueError("模型权重必须为 model.pt，格式必须为 state_dict")
        digest = self.weights.get("sha256", "").removeprefix("sha256:")
        if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise ValueError("模型权重缺少有效 SHA256 哈希，请重新导出模型")
        if self.trained_on.get("source") == "arena" and not all(
            key in self.trained_on for key in ("dataset_config", "generator_version")
        ):
            raise ValueError("Arena 训练数据必须记录配置和生成器版本")
        if self.output.type == "grid_probability" and self.output.grid is None:
            raise ValueError("网格概率输出必须声明角度网格")
        return self

    @property
    def generator_version(self) -> int | None:
        """训练数据的信号生成器版本。"""
        return self.trained_on.get("generator_version")

    @classmethod
    def from_file(cls, path: str | Path) -> ModelMeta:
        """读取模型目录或 model.json，保留运行时绝对路径。"""
        source = Path(path).resolve()
        if source.is_dir():
            source = source / "model.json"
        data = json.loads(source.read_text(encoding="utf-8"))
        data["path"] = source.parent
        return cls.model_validate(data)

    def verify_weights(self) -> None:
        """流式核对权重哈希；在反序列化前执行。"""
        digest = hashlib.sha256()
        with (self.path / "model.pt").open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        if digest.hexdigest() != self.weights["sha256"].removeprefix("sha256:"):
            raise ValueError("模型权重哈希不符，请重新导入完整模型包")

    def to_file(self, path: Path) -> None:
        """原子保存模型说明。"""
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, delete=False
        ) as stream:
            stream.write(self.model_dump_json(indent=2))
            temporary = Path(stream.name)
        try:
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)
