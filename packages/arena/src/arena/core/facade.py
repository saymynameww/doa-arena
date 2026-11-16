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
from .config.scenario import ArrayConfig, ImpairmentConfig
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
        manifest = self.path / "arena_workspace.json"
        if not manifest.exists():
            ResultWriter(self.path)._write_json(
                manifest,
                {
                    "schema_version": 1,
                    "name": self.path.name,
                    "algorithm_sources": [],
                    "created_at": datetime.now().astimezone().isoformat(),
                },
            )
        ignore = self.path / ".gitignore"
        if not ignore.exists():
            ignore.write_text(
                ".arena_index.sqlite\n.trash/\nexperiments/*/points/\nexperiments/*/*.npz\nexperiments/*/exports/\ndatasets/\nmodels/*/*.pt\n",
                encoding="utf-8",
            )

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
    source = None
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
    manifest = json.loads((ws.path / "arena_workspace.json").read_text(encoding="utf-8"))
    sources = manifest.get("algorithm_sources", [])
    if sources:
        from .plugins import discover

        registry = discover(sources)
        for item in parsed.algorithms:
            if item.get_label() not in classes and item.origin is None:
                entry = next((p for p in registry["algorithms"] if p["id"] == item.id), None)
                if entry is not None:
                    item.origin = entry["origin"]
        targets: list[tuple[ArrayConfig | ImpairmentConfig, str]] = [
            (parsed.scenario.array, "arrays"),
            *((i, "impairments") for i in parsed.scenario.impairments),
        ]
        for component, category in targets:
            entry = next((p for p in registry[category] if p["id"] == component.type), None)
            if entry is not None and component.origin is None:
                component.origin = entry["origin"]
        for name in parsed.metrics.include:
            name = "resolution_prob" if name == "resolution" else name
            entry = next((p for p in registry["metrics"] if p["id"] == name), None)
            if entry is not None and entry["origin"]:
                parsed.metrics.origins[name] = entry["origin"]
    experiment_id = datetime.now().strftime("%Y%m%d-%H%M%S") + "_experiment_" + uuid.uuid4().hex[:8]
    output = ws.experiments / experiment_id
    writer = ResultWriter(output)
    if source is not None and source.suffix.lower() in {".yaml", ".yml"}:
        (output / "config.source.yaml").write_text(
            source.read_text(encoding="utf-8"), encoding="utf-8"
        )
    import logging

    handler = logging.FileHandler(output / "log.txt", encoding="utf-8")
    log = logging.getLogger("arena.core")
    log.addHandler(handler)
    try:
        result = run_experiment(
            parsed, algorithm_classes=classes, checkpoint_callback=writer.write_experiment
        )
    finally:
        log.removeHandler(handler)
        handler.close()
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


def recompute_metrics(
    directory: str | Path,
    metrics: dict[str, Any],
) -> ExperimentResult:
    """只更新指标数组和汇总，保留原始估计、真值及历史设置。"""
    import hashlib
    import json

    import numpy as np

    from .config.experiment import MetricsConfig

    output = Path(directory)
    result = read_result(output)
    if not result.config.get("options", {}).get("save_estimates", True):
        raise ValueError("此实验未保存逐次估计，无法重算指标，请重新运行并开启保存估计")
    previous = result.config["metrics"]
    merged = {
        **previous,
        **metrics,
        "params": {**previous.get("params", {}), **metrics.get("params", {})},
    }
    result.config["metrics"] = MetricsConfig.model_validate(merged).model_dump(mode="json")
    result.metadata.setdefault("history", []).append(
        {
            "at": datetime.now().astimezone().isoformat(),
            "action": "recompute_metrics",
            "old_metrics": previous,
            "previous_metrics": previous,
            "new_metrics": result.config["metrics"],
        }
    )
    writer = ResultWriter(output)
    writer._write_summary(result)
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    with np.load(output / "results.npz", allow_pickle=False) as saved:
        arrays = {
            name: saved[name]
            for name in saved.files
            if not name.startswith("metric__") and name not in {"crb", "crb_per_source"}
        }
    for identifier, metric in summary["metrics"].items():
        arrays[f"metric__{identifier}__value"] = np.asarray(metric["value"], dtype=float)
        arrays[f"metric__{identifier}__n_used"] = np.asarray(metric["n_used"], dtype=np.int32)
    if summary.get("crb"):
        arrays["crb"] = np.asarray(summary["crb"]["value"], dtype=float)
    from .metrics.summary import algorithm_labels
    from .storage.contract import standard_arrays

    refreshed = standard_arrays(result, algorithm_labels(result), summary)
    arrays.update(
        {
            key: value
            for key, value in refreshed.items()
            if key.startswith("metric__") or key in {"crb", "crb_per_source"}
        }
    )
    writer._write_npz(output / "results.npz", arrays)
    document = ExperimentConfig.model_validate(result.config).to_document()
    result.metadata["config_hash"] = (
        "sha256:"
        + hashlib.sha256(
            json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
                "utf-8"
            )
        ).hexdigest()
    )
    writer._write_json(output / "config.json", document)
    writer._write_json(output / "meta.json", result.metadata)
    result.saved_summary = summary
    return result


def finalize(
    experiment_id: str, workspace: Workspace | str | Path = "arena_workspace"
) -> ExperimentResult:
    """整理中断实验，保留可恢复的逐次结果并标记为部分完成。"""
    from .storage.finalize import finalize_directory

    ws = workspace if isinstance(workspace, Workspace) else Workspace(workspace)
    if Path(experiment_id).name != experiment_id or experiment_id in {".", ".."}:
        raise ValueError("实验 ID 必须是单个目录名")
    return finalize_directory(ws.experiments / experiment_id)
