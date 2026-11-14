"""学习型模型元数据定义。"""

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class ModelMeta(BaseModel):
    """模型元数据（model.json）。

    随模型包提供，描述模型的输入输出格式、训练条件等。
    """

    # 基本信息
    model_name: str = Field(..., description="模型名称")
    algorithm_id: str = Field(..., description="算法插件 id")

    # 阵列
    array: dict[str, Any] = Field(
        ...,
        description="训练时的阵列配置，如 {'type': 'ula', 'params': {'M': 16, 'd': 0.5}}",
    )

    # 输入输出
    input: str = Field(..., description="输入格式描述")
    output: dict[str, Any] = Field(..., description="输出格式，如 {'type': 'grid_probability', 'grid': {...}}")

    # 训练条件
    trained_on: dict[str, Any] = Field(
        default_factory=dict,
        description="训练数据范围，如 {'snr_db': [-10, 20], 'K': [1, 3]}",
    )

    # 框架信息
    framework: str = Field(default="pytorch", description="深度学习框架")
    torch_version: str | None = Field(default=None, description="PyTorch 版本")

    # 由导出函数自动填充（可选）
    arena_version: str | None = None
    arena_api_version: str | None = None
    generator_version: int | None = None
    training_config_path: Path | None = None
    training_commit: str | None = None
    created_at: str | None = None
    weights_sha256: str | None = None

    @classmethod
    def from_file(cls, path: Path) -> "ModelMeta":
        """从 JSON 文件加载。"""
        import json

        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return cls(**data)

    def to_file(self, path: Path) -> None:
        """保存为 JSON 文件。"""
        import json

        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.model_dump(), f, indent=2, ensure_ascii=False)
