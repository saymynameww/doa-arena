"""脚本模式门面；调用同一核心执行器和文件格式。"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from arena_api import Algorithm, ParamsModel
from arena_api.plugin import AlgorithmSpec

from .config import AlgorithmConfig, ExperimentConfig
from .plugins import builtin_classes, provenance
from .runner.core import run_experiment
from .runner.results import ExperimentResult
from .storage import ResultWriter
from .storage.reader import read_result


@dataclass
class Workspace:
    """脚本和 Web 共享的工作目录。"""

    path: Path

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).expanduser().resolve()
        self.experiments.mkdir(parents=True, exist_ok=True)

    @property
    def experiments(self) -> Path:
        """实验文件目录。"""
        return self.path / "experiments"


def algorithm_spec(id: str, label: str | None = None, **params: Any) -> AlgorithmConfig:
    """为内置算法生成已校验的配置描述。"""
    classes = builtin_classes()
    if id not in classes:
        raise ValueError(f"算法 {id} 未登记，外部类请使用 Algorithm.spec()")
    validated = classes[id].Params.model_validate(params)
    return AlgorithmConfig(
        id=id, label=label, enabled=True, params=validated.model_dump(mode="json")
    )


def run(
    config: dict[str, Any] | ExperimentConfig | str | Path,
    workspace: Workspace | str | Path = "arena_workspace",
) -> ExperimentResult:
    """在调用进程内执行并保存完整实验，允许直接传入调试算法类。"""
    ws = workspace if isinstance(workspace, Workspace) else Workspace(workspace)
    if isinstance(config, str | Path):
        source = Path(config)
        if source.suffix.lower() in {".yaml", ".yml"}:
            import yaml

            document = yaml.safe_load(source.read_text(encoding="utf-8"))
        else:
            document = json.loads(source.read_text(encoding="utf-8"))
    elif isinstance(config, ExperimentConfig):
        document = config.model_dump(mode="json")
    else:
        document = dict(config)
    classes: dict[str, type[Algorithm]] = {}
    algorithms = []
    for entry in document.get("algorithms", []):
        if isinstance(entry, AlgorithmSpec):
            classes[entry.label] = entry.algorithm_class
            params = (
                entry.params.model_dump(mode="json")
                if isinstance(entry.params, ParamsModel)
                else entry.params
            )
            algorithms.append(
                AlgorithmConfig(
                    id=entry.algorithm_class.id,
                    enabled=True,
                    label=entry.label,
                    params=params,
                    origin=provenance(entry.algorithm_class),
                )
            )
        else:
            algorithms.append(entry)
    document["algorithms"] = algorithms
    parsed = ExperimentConfig.model_validate(document)
    experiment_id = datetime.now().strftime("%Y%m%d-%H%M%S") + "_experiment_" + uuid.uuid4().hex[:8]
    output = ws.experiments / experiment_id
    writer = ResultWriter(output)
    result = run_experiment(
        parsed, algorithm_classes=classes, checkpoint_callback=writer.write_experiment
    )
    result.metadata.update(experiment_id=experiment_id, directory=str(output))
    writer.write_experiment(result)
    writer._write_json(output / "status.json", {"schema_version": 1, "status": "completed"})
    return result


def load_result(workspace: Workspace | str | Path, experiment_id: str) -> ExperimentResult:
    """按工作目录和实验 ID 恢复结果。"""
    ws = workspace if isinstance(workspace, Workspace) else Workspace(workspace)
    if Path(experiment_id).name != experiment_id or experiment_id in {".", ".."}:
        raise ValueError("实验 ID 必须是单个目录名")
    return read_result(ws.experiments / experiment_id)
