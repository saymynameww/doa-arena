"""数据格式规范第 5 章：可恢复的数据生成和全局索引读取。"""

from __future__ import annotations

import copy
import hashlib
import json
import platform
from datetime import datetime, timezone
from itertools import pairwise
from pathlib import Path
from typing import Any, Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator

from arena_api import AngleGrid

from .config import ExperimentConfig
from .rng import TrialRNG
from .runner.core import GENERATOR_VERSION, build_scene
from .storage.writer import ResultWriter


class GridLabelsConfig(BaseModel):
    """网格标签配置。"""

    model_config = ConfigDict(extra="forbid")
    grid: AngleGrid
    sigma_deg: float | None = Field(None, gt=0)


class DatasetContent(BaseModel):
    """分片内容选项。"""

    model_config = ConfigDict(extra="forbid")
    observation: Literal["R", "X", "both"] = "R"
    grid_labels: GridLabelsConfig | None = None


def distribution_values(value: Any) -> list[float]:
    """返回分布的边界或离散支持集，并拒绝非法分布。"""
    if isinstance(value, bool):
        raise ValueError("数值分布不能使用布尔值")
    if isinstance(value, int | float):
        if not np.isfinite(value):
            raise ValueError("数值必须有限")
        return [value]
    if not isinstance(value, dict) or len(value) != 1:
        raise ValueError("分布只能使用 uniform、uniform_int 或 choice 的单个键")
    kind, values = next(iter(value.items()))
    if kind not in {"uniform", "uniform_int", "choice"} or not isinstance(values, list):
        raise ValueError("未知数值分布，请使用 uniform、uniform_int 或 choice")
    if not values or any(isinstance(x, bool) or not isinstance(x, int | float) for x in values):
        raise ValueError("分布必须包含有限数值")
    if not np.all(np.isfinite(values)):
        raise ValueError("分布必须包含有限数值")
    if kind != "choice" and (len(values) != 2 or values[0] > values[1]):
        raise ValueError("分布范围必须包含有序的两个端点")
    if kind == "uniform_int" and any(not isinstance(x, int) for x in values):
        raise ValueError("uniform_int 两端必须为整数")
    return values


def _distributions(node: Any, path: str = "scenario") -> list[tuple[str, dict[str, Any]]]:
    result: list[tuple[str, dict[str, Any]]] = []
    if isinstance(node, dict):
        if set(node) & {"uniform", "uniform_int", "choice"}:
            distribution_values(node)
            result.append((path, node))
        else:
            for key, value in node.items():
                result.extend(_distributions(value, f"{path}.{key}"))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            result.extend(_distributions(value, f"{path}[{index}]"))
    return result


def _realize(node: Any, seed: int, index: int, path: str = "scenario") -> Any:
    if isinstance(node, dict):
        if set(node) & {"uniform", "uniform_int", "choice"}:
            key, values = next(iter(node.items()))
            token = int.from_bytes(hashlib.sha256(path.encode("utf-8")).digest()[:4], "little")
            rng = np.random.default_rng(np.random.SeedSequence(seed, spawn_key=(2, index, token)))
            if key == "choice":
                return np.asarray(rng.choice(values)).item()
            if key == "uniform_int":
                return int(rng.integers(values[0], values[1] + 1))
            return float(rng.uniform(*values))
        return {k: _realize(v, seed, index, f"{path}.{k}") for k, v in node.items()}
    if isinstance(node, list):
        return [_realize(v, seed, index, f"{path}[{i}]") for i, v in enumerate(node)]
    return node


class DatasetConfig(BaseModel):
    """支持数值分布的数据集配置；生成前检查结构与支持范围。"""

    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[1] = 1
    name: str = "训练数据"
    seed: int = Field(42, ge=0, lt=2**63)
    num_samples: int = Field(..., ge=1, le=10**9)
    shard_size: int = Field(10000, ge=1)
    scenario: dict[str, Any]
    content: DatasetContent = Field(default_factory=DatasetContent)

    @model_validator(mode="after")
    def validate_ranges(self) -> DatasetConfig:
        """只允许设计文档列出的分布字段，并检查形状约束。"""
        import re

        from .config.scenario import (
            AnglesConfig,
            ArrayConfig,
            CorrelationConfig,
            ImpairmentConfig,
            ScenarioConfig,
            SourcesConfig,
        )

        def check_keys(value: dict[str, Any], fields: set[str], path: str) -> None:
            unknown = set(value) - fields
            if unknown:
                raise ValueError(f"{path} 含未知字段 {sorted(unknown)}，请检查拼写")

        check_keys(self.scenario, set(ScenarioConfig.model_fields) | {"carrier_hz"}, "scenario")
        check_keys(self.scenario.get("array", {}), set(ArrayConfig.model_fields), "array")
        sources = self.scenario.get("sources", {})
        check_keys(sources, set(SourcesConfig.model_fields), "sources")
        check_keys(
            sources.get("angles", {}), set(AnglesConfig.model_fields) | {"min", "max"}, "angles"
        )
        correlation = sources.get("correlation", {})
        check_keys(correlation, set(CorrelationConfig.model_fields) | {"rho"}, "correlation")
        check_keys(correlation.get("rho", {}), {"mag", "phase_deg"}, "rho")
        for impairment in self.scenario.get("impairments", []):
            check_keys(impairment, set(ImpairmentConfig.model_fields), "impairment")
        for path, distribution in _distributions(self.scenario):
            allowed = path in {
                "scenario.sources.K",
                "scenario.sources.snr_db",
                "scenario.snapshots",
                "scenario.sources.correlation.rho.mag",
                "scenario.sources.correlation.rho.phase_deg",
            } or re.fullmatch(
                r"scenario\.impairments\[\d+\]\.params\.[a-zA-Z_][a-zA-Z_0-9.\[\]]*", path
            )
            if not allowed:
                raise ValueError(f"字段 {path} 不允许分布")
            if path in {"scenario.sources.K", "scenario.snapshots"}:
                if "uniform" in distribution or any(
                    not isinstance(x, int) or x < 1 for x in distribution_values(distribution)
                ):
                    raise ValueError(f"{path} 必须使用正整数离散分布")
        sources = self.scenario.get("sources", {})
        if isinstance(sources.get("snr_db", 10), list):
            raise ValueError("数据集 SNR 必须是单值或分布，不接受逐信源列表")
        snapshots = self.scenario.get("snapshots", 100)
        if self.content.observation != "R" and isinstance(snapshots, dict):
            raise ValueError("保存 X 时快拍数必须固定，请选择 R 或固定快拍数")
        k_values = distribution_values(sources.get("K", 2))
        if isinstance(sources.get("K"), dict) and sources.get("angles", {}).get("mode") != "random":
            raise ValueError("随机信源数要求随机角度模式")
        for k in {min(k_values), max(k_values)}:
            sample = _realize(self.scenario, self.seed, 0)
            sample.setdefault("sources", {})["K"] = int(k)
            build_scene(ExperimentConfig.model_validate({"scenario": sample}))
        for path, distribution in _distributions(self.scenario):
            for edge in {
                min(distribution_values(distribution)),
                max(distribution_values(distribution)),
            }:
                sample = _realize(self.scenario, self.seed, 0)
                node = sample
                tokens = re.findall(r"[^.\[\]]+", path)[1:]
                for token in tokens[:-1]:
                    node = node[int(token)] if isinstance(node, list) else node[token]
                key = int(tokens[-1]) if isinstance(node, list) else tokens[-1]
                node[key] = edge
                parsed = ExperimentConfig.model_validate({"scenario": sample})
                from .plugins import resolve_plugin

                _, array = build_scene(parsed)
                for item in parsed.scenario.impairments:
                    cls = resolve_plugin("impairment", item.type, item.origin)
                    errors = [
                        issue.message
                        for issue in cls.check(cls.Params(**item.params), array.M)
                        if issue.level == "error"
                    ]
                    if errors:
                        raise ValueError("；".join(errors))
        correlation = sources.get("correlation", {})
        if correlation.get("mode") == "partial":
            _check_correlation_support(correlation, int(max(k_values)))
        if self.content.grid_labels:
            parsed = ExperimentConfig.model_validate(
                {"scenario": _realize(self.scenario, self.seed, 0)}
            )
            angles = parsed.scenario.sources.angles
            if angles.mode == "random":
                bounds = list(angles.range_deg or [])
            elif angles.mode == "separation":
                bounds = [
                    angles.center - (angles.delta or 0) / 2,
                    angles.center + (angles.delta or 0) / 2,
                ]
            else:
                bounds = angles.values or []
            for angle in bounds:
                self.content.grid_labels.grid.index(angle)
        return self


def _check_correlation_support(correlation: dict[str, Any], kmax: int) -> None:
    """在相位支持区间求最差特征值，避免仅检查一次随机抽样。"""
    from scipy.optimize import minimize_scalar

    rho = correlation.get("rho", {})
    magnitude = max(distribution_values(rho.get("mag", correlation.get("rho_mag", 0))))
    phase = rho.get("phase_deg", correlation.get("rho_phase_deg", 0))
    phases = distribution_values(phase)

    def smallest(angle: float) -> float:
        value = magnitude * np.exp(1j * np.deg2rad(angle))
        upper = np.triu(np.full((kmax, kmax), value), 1)
        return float(np.linalg.eigvalsh(np.eye(kmax) + upper + upper.conj().T)[0])

    minimum = min(smallest(value) for value in phases)
    if isinstance(phase, dict) and "uniform" in phase:
        low, high = phases
        # 矩阵以 360° 为周期，分段优化覆盖整个相位区间及内部最小值。
        high = min(high, low + 360)
        bounds = np.linspace(low, high, 73)
        for left, right in pairwise(bounds):
            if right > left:
                minimum = min(
                    minimum,
                    float(minimize_scalar(smallest, bounds=(left, right), method="bounded").fun),
                )
    if minimum < -1e-10:
        raise ValueError("相关系数分布包含非半正定协方差，请减小幅度或缩小相位范围")


def grid_labels(angles: np.ndarray, grid: AngleGrid, sigma: float | None = None) -> np.ndarray:
    """生成多热或逐信源高斯取最大值的标签（架构 5.10）。"""
    labels = np.zeros(grid.size, dtype=np.float32)
    for angle in np.asarray(angles):
        index = grid.index(float(angle))
        if sigma is None:
            labels[index] = 1
        else:
            if not np.isfinite(sigma) or sigma <= 0:
                raise ValueError("高斯标签 sigma 必须大于零")
            labels = np.maximum(labels, np.exp(-0.5 * ((grid.points - angle) / sigma) ** 2))
    return labels.astype(np.float32)


def sample(config: DatasetConfig, index: int) -> dict[str, np.ndarray]:
    """生成全局索引样本；训练分支与评测分支隔离，计算使用双精度。"""
    if not 0 <= index < config.num_samples:
        raise IndexError("样本索引超出数据集范围")
    data = _realize(config.scenario, config.seed, index)
    # 数据集根种子具有独立命名空间；固定误差在所有样本间保持相同。
    dataset_seed = int(np.random.SeedSequence(config.seed, spawn_key=(2,)).generate_state(1)[0])
    data["seed"] = dataset_seed
    scene, _ = build_scene(ExperimentConfig.model_validate({"scenario": data}), index)
    obs = scene.generate(TrialRNG(np.random.SeedSequence(config.seed, spawn_key=(2, index))))
    kmax = int(max(distribution_values(config.scenario.get("sources", {}).get("K", 2))))
    angles = np.full(kmax, np.nan, dtype=np.float32)
    angles[: obs.K] = np.sort(scene.config.angles)
    result: dict[str, np.ndarray] = {
        "index": np.asarray(index, dtype=np.int64),
        "angles": angles,
        "K": np.asarray(obs.K, dtype=np.int16),
        "snr_db": np.asarray(scene.config.snr_db, dtype=np.float32),
        "snapshots": np.asarray(obs.N, dtype=np.int32),
    }
    if config.content.observation in {"R", "both"}:
        result["R"] = obs.covariance().astype(np.complex64)
    if config.content.observation in {"X", "both"}:
        result["X"] = obs.X.astype(np.complex64)
    labels = config.content.grid_labels
    if labels is not None:
        result["labels"] = grid_labels(scene.config.angles, labels.grid, labels.sigma_deg)
    for j, (path, _) in enumerate(_sampled_params(config)):
        import re

        value = data
        for token in re.findall(r"[^.\[\]]+", path)[1:]:
            value = value[int(token)] if isinstance(value, list) else value[token]
        result[f"param__{j}"] = np.asarray(value, dtype=np.float32)
    return result


def _sampled_params(config: DatasetConfig) -> list[tuple[str, dict[str, Any]]]:
    return [
        (p, d)
        for p, d in _distributions(config.scenario)
        if p
        not in {
            "scenario.sources.K",
            "scenario.sources.snr_db",
            "scenario.snapshots",
        }
    ]


def _digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def read_config(config: DatasetConfig | dict[str, Any] | str | Path) -> DatasetConfig:
    """读取配置对象、JSON 或 YAML。"""
    if isinstance(config, str | Path):
        import yaml

        config = yaml.safe_load(Path(config).read_text(encoding="utf-8"))
    return DatasetConfig.model_validate(config)


def generate(
    config: DatasetConfig | dict[str, Any] | str | Path,
    out_dir: str | Path,
    *,
    start: int = 0,
    stop: int | None = None,
) -> Path:
    """按全局区间生成分片，重复调用校验已有分片并恢复未完成数据。"""
    from filelock import FileLock, Timeout

    directory = Path(out_dir)
    directory.mkdir(parents=True, exist_ok=True)
    try:
        with FileLock(directory / ".generate.lock", timeout=0):
            return _generate(config, directory, start=start, stop=stop)
    except Timeout as exc:
        raise ValueError("此数据集正在被另一进程写入，请稍后重试；不同输出目录可并行生成") from exc


def _generate(
    config: DatasetConfig | dict[str, Any] | str | Path,
    out_dir: str | Path,
    *,
    start: int = 0,
    stop: int | None = None,
) -> Path:
    import arena
    import arena_api

    original = config
    cfg = read_config(config)
    stop = cfg.num_samples if stop is None else stop
    if not 0 <= start < stop <= cfg.num_samples:
        raise ValueError("生成区间必须满足 0 ≤ start < stop ≤ num_samples")
    directory = Path(out_dir)
    directory.mkdir(parents=True, exist_ok=True)
    writer = ResultWriter(directory)
    document = cfg.model_dump(mode="json")
    fingerprint = (
        "sha256:"
        + hashlib.sha256(
            json.dumps(document, sort_keys=True, ensure_ascii=True).encode("utf-8")
        ).hexdigest()
    )
    manifest_path = directory / "dataset.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest["config_hash"] != fingerprint:
            raise ValueError("目录中已有不同配置的数据集，请更换输出目录")
        for shard in manifest["shards"]:
            if _digest(directory / shard["file"]) != shard["sha256"]:
                raise ValueError(f"分片 {shard['file']} 哈希不符，请恢复原始文件")
    else:
        manifest = {
            "schema_version": 1,
            "id": fingerprint.split(":")[1][:16],
            "name": cfg.name,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "finished_at": None,
            "config": document,
            "config_hash": fingerprint,
            "status": "generating",
            "versions": {
                "arena": arena.__version__,
                "arena_api": arena_api.__version__,
                "generator": GENERATOR_VERSION,
            },
            "environment": {
                "os": platform.system(),
                "python": platform.python_version(),
                "numpy": np.__version__,
            },
            "num_samples": cfg.num_samples,
            "sampled_params": [p for p, _ in _sampled_params(cfg)],
            "arrays": {},
            "shards": [],
        }
        writer._write_json(manifest_path, manifest)
    if isinstance(original, str | Path) and Path(original).suffix.lower() in {".yaml", ".yml"}:
        (directory / "dataset.source.yaml").write_text(
            Path(original).read_text(encoding="utf-8"), encoding="utf-8"
        )
    existing = [(s["start"], s["start"] + s["count"]) for s in manifest["shards"]]
    cursor = start
    while cursor < stop:
        covering = next((b for a, b in existing if a <= cursor < b), None)
        if covering is not None:
            cursor = covering
            continue
        end = min(
            stop, cursor + cfg.shard_size, min((a for a, _ in existing if a > cursor), default=stop)
        )
        samples = [sample(cfg, i) for i in range(cursor, end)]
        arrays = {key: np.stack([s[key] for s in samples]) for key in samples[0]}
        filename = f"shard_{cursor:09d}.npz"
        writer._write_npz(directory / filename, arrays)
        manifest["shards"].append(
            {
                "file": filename,
                "start": cursor,
                "count": end - cursor,
                "sha256": _digest(directory / filename),
            }
        )
        manifest["shards"].sort(key=lambda s: s["start"])
        manifest["arrays"] = {
            key: {"dtype": str(value.dtype), "shape": list(value.shape[1:])}
            for key, value in arrays.items()
        }
        complete = sum(s["count"] for s in manifest["shards"]) == cfg.num_samples
        manifest["status"] = "complete" if complete else "generating"
        if complete:
            manifest["finished_at"] = datetime.now(timezone.utc).isoformat()
        writer._write_json(manifest_path, manifest)
        cursor = end
    return directory


class Dataset:
    """按全局索引读取分片，返回只读数组，不依赖 PyTorch。"""

    def __init__(self, directory: str | Path) -> None:
        self.directory = Path(directory)
        self.manifest = json.loads((self.directory / "dataset.json").read_text(encoding="utf-8"))
        self._cached_file: str | None = None
        self._cached: dict[str, np.ndarray] = {}

    def __len__(self) -> int:
        return int(self.manifest["num_samples"])

    def __getitem__(self, index: int) -> dict[str, np.ndarray]:
        if not 0 <= index < len(self):
            raise IndexError("样本索引超出数据集范围")
        shard = next(
            (s for s in self.manifest["shards"] if s["start"] <= index < s["start"] + s["count"]),
            None,
        )
        if shard is None:
            raise IndexError("该全局索引尚未生成，请继续生成相应区间")
        if self._cached_file != shard["file"]:
            path = self.directory / shard["file"]
            if _digest(path) != shard["sha256"]:
                raise ValueError("数据分片哈希不符，请检查文件是否损坏")
            with np.load(path, allow_pickle=False) as arrays:
                self._cached = {key: arrays[key] for key in arrays.files}
            self._cached_file = shard["file"]
        result = {
            key: np.asarray(value[index - shard["start"]]).copy()
            for key, value in self._cached.items()
        }
        for value in result.values():
            value.flags.writeable = False
        return result


class TorchDataset:
    """DataLoader 支持的映射式数据集，torch 仅在构造时延迟导入。"""

    def __init__(
        self,
        source: str | Path | dict[str, Any] | DatasetConfig,
        size: int | None = None,
        seed: int | None = None,
    ) -> None:
        import torch  # noqa: F401

        self.offline: Dataset | None = None
        self.config: DatasetConfig | None = None
        if isinstance(source, str | Path) and Path(source).is_dir():
            self.offline = Dataset(source)
        else:
            data = (
                read_config(source).model_dump(mode="json")
                if isinstance(source, DatasetConfig | str | Path)
                else copy.deepcopy(source)
            )
            if size is not None:
                data["num_samples"] = size
            if seed is not None:
                data["seed"] = seed
            self.config = read_config(data)

    def __len__(self) -> int:
        return len(self.offline) if self.offline is not None else self.config.num_samples  # type: ignore[union-attr]

    def __getitem__(self, index: int) -> dict[str, Any]:
        import torch

        arrays = self.offline[index] if self.offline is not None else sample(self.config, index)  # type: ignore[arg-type]
        return {key: torch.from_numpy(value.copy()) for key, value in arrays.items()}
