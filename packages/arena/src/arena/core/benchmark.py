"""版本化场景集、普通实验评测记录及可追溯排行榜（数据格式 7.4）。"""

from __future__ import annotations

import hashlib
import json
import math
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .config import AlgorithmConfig, ExperimentConfig
from .facade import Workspace
from .storage.writer import ResultWriter

BUILTIN_DIRECTORY = Path(__file__).resolve().parents[1] / "benchmarks"


class BenchmarkScenario(BaseModel):
    """一个不含算法选择的固定实验。"""

    model_config = ConfigDict(extra="forbid")
    name: str = Field(pattern=r"^[a-zA-Z0-9_-]+$")
    description: str = ""
    config: dict[str, Any]


class LeaderboardColumn(BaseModel):
    """排行榜明确指定场景、指标与扫描点，不跨点求平均。"""

    model_config = ConfigDict(extra="forbid")
    scenario: str
    metric: str
    at: int = Field(ge=0)
    label: str


class BenchmarkSuite(BaseModel):
    """不可变版本的标准或自定义场景集。"""

    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[1] = 1
    suite_id: str = Field(pattern=r"^[a-zA-Z0-9_-]+$")
    version: str = Field(pattern=r"^[a-zA-Z0-9_.-]+$")
    name: str
    scenarios: list[BenchmarkScenario] = Field(min_length=1)
    leaderboard: list[LeaderboardColumn] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_suite(self) -> BenchmarkSuite:
        """检查固定种子、场景唯一性和排行榜点位。"""
        configs = {}
        for scenario in self.scenarios:
            if scenario.name in configs:
                raise ValueError("场景名称不能重复")
            if "algorithms" in scenario.config or "name" in scenario.config:
                raise ValueError("场景配置不能包含 algorithms 或 name")
            if "seed" not in scenario.config and "seed" not in scenario.config.get("scenario", {}):
                raise ValueError("场景必须显式声明 seed，保证评测可复现")
            configs[scenario.name] = ExperimentConfig.model_validate(scenario.config)
        for column in self.leaderboard:
            if column.scenario not in configs:
                raise ValueError("排行榜引用了不存在的场景")
            config = configs[column.scenario]
            count = len(config.sweep.values) if config.type == "sweep" and config.sweep else 1
            if column.at >= count:
                raise ValueError("排行榜扫描点序号越界")
            metrics = [
                "resolution_prob" if m == "resolution" else m for m in config.metrics.include
            ]
            if column.metric not in metrics or column.metric == "crb":
                raise ValueError("排行榜指标必须是场景已计算的算法指标")
        return self

    @property
    def digest(self) -> str:
        """对版本内容计算稳定哈希。"""
        return (
            "sha256:"
            + hashlib.sha256(
                json.dumps(self.model_dump(mode="json"), sort_keys=True, ensure_ascii=True).encode(
                    "utf-8"
                )
            ).hexdigest()
        )


def list_suites(workspace: str | Path) -> list[dict[str, Any]]:
    """列出内置和自定义场景集；同版本冲突不静默覆盖。"""
    builtins = (
        json.loads((BUILTIN_DIRECTORY / "hashes.json").read_text(encoding="utf-8"))
        if (BUILTIN_DIRECTORY / "hashes.json").exists()
        else {}
    )
    entries: dict[tuple[str, str], dict[str, Any]] = {}
    for directory, builtin in (
        (BUILTIN_DIRECTORY, True),
        (Path(workspace) / "benchmarks/suites", False),
    ):
        for path in sorted(directory.glob("*.json")):
            if path.name == "hashes.json":
                continue
            suite = BenchmarkSuite.model_validate_json(path.read_text(encoding="utf-8"))
            if builtin and builtins.get(path.name) != suite.digest:
                raise ValueError("内置场景集哈希不符，请恢复发行版文件，不可修改已发布版本")
            key = (suite.suite_id, suite.version)
            if key in entries and entries[key]["hash"] != suite.digest:
                raise ValueError("场景集相同版本内容冲突，请为修改后的场景升版本")
            entries[key] = {
                **suite.model_dump(mode="json"),
                "hash": suite.digest,
                "builtin": builtin,
            }
    return list(entries.values())


def load_suite(workspace: str | Path, suite_id: str, version: str) -> BenchmarkSuite:
    """精确选择场景集版本。"""
    for entry in list_suites(workspace):
        if entry["suite_id"] == suite_id and entry["version"] == version:
            return BenchmarkSuite.model_validate(
                {k: v for k, v in entry.items() if k not in {"hash", "builtin"}}
            )
    raise ValueError("未找到指定场景集版本，请刷新场景集列表")


def save_suite(document: dict[str, Any], workspace: str | Path) -> dict[str, Any]:
    """导入自定义场景集；同版本相同内容幂等，不同内容拒绝。"""
    suite = BenchmarkSuite.model_validate(document)
    for entry in list_suites(workspace):
        if entry["suite_id"] == suite.suite_id and entry["version"] == suite.version:
            if entry["hash"] != suite.digest:
                raise ValueError("该场景集版本已存在且内容不同，请递增版本号")
            return entry
    directory = Path(workspace) / "benchmarks/suites"
    ResultWriter(directory)._write_json(
        directory / f"{suite.suite_id}--{suite.version}.json", suite.model_dump(mode="json")
    )
    return {**suite.model_dump(mode="json"), "hash": suite.digest, "builtin": False}


def create_run(
    workspace: str | Path,
    suite_id: str,
    version: str,
    algorithms: list[dict[str, Any]],
    scenarios: list[str] | None = None,
) -> dict[str, Any]:
    """先校验整组配置，再创建关联的普通实验与评测记录。"""
    from .plugins import discover
    from .validation import validate_configuration

    ws = Workspace(workspace)
    suite = load_suite(ws.path, suite_id, version)
    selected = [s for s in suite.scenarios if scenarios is None or s.name in scenarios]
    invalid = scenarios is not None and set(scenarios) - {s.name for s in suite.scenarios}
    if not selected or invalid:
        raise ValueError("请选择场景集内至少一个场景")
    manifest = json.loads((ws.path / "arena_workspace.json").read_text(encoding="utf-8"))
    sources = manifest.get("algorithm_sources", [])
    for source in sources:
        if source.get("type") == "path" and not Path(source["value"]).is_absolute():
            source["value"] = str(ws.path / source["value"])
    registry = discover(sources)
    choices = []
    for entry in algorithms:
        item = AlgorithmConfig.model_validate(entry)
        if not item.enabled:
            continue
        if item.origin is None:
            plugin = next((p for p in registry["algorithms"] if p["id"] == item.id), None)
            if plugin:
                item.origin = plugin["origin"]
        choices.append(item.model_dump(mode="json"))
    if not choices:
        raise ValueError("请先在新建实验页配置并启用至少一个算法")
    # 新评测的算法选择按当前协议记录，避免缺省参数与旧榜单混为同一变体。
    choices = ExperimentConfig.model_validate({"algorithms": choices}).model_dump(mode="json")[
        "algorithms"
    ]
    configs = {}
    for scenario in selected:
        scene_document = ExperimentConfig.model_validate(scenario.config).model_dump(mode="json")
        config = ExperimentConfig.model_validate(
            {**scene_document, "name": f"{suite_id}/{scenario.name}", "algorithms": choices}
        )
        config._workspace = ws.path
        validate_configuration(config)
        configs[scenario.name] = config
    run_id = datetime.now().strftime("%Y%m%d-%H%M%S") + "_bench_" + uuid.uuid4().hex[:8]
    record: dict[str, Any] = {
        "schema_version": 1,
        "run_id": run_id,
        "suite_id": suite_id,
        "suite_version": version,
        "suite_hash": suite.digest,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "algorithms": choices,
        "experiments": {},
    }
    writer = ResultWriter(ws.path / "benchmarks/runs")
    for name, config in configs.items():
        experiment_id = run_id + "_" + name
        directory = ws.experiments / experiment_id
        experiment_writer = ResultWriter(directory)
        experiment_writer._write_json(directory / "config.json", config.to_document())
        experiment_writer._write_json(
            directory / "benchmark.json",
            {
                "suite_id": suite_id,
                "version": version,
                "run_id": run_id,
                "scenario_name": name,
                "suite_hash": suite.digest,
            },
        )
        experiment_writer._write_json(
            directory / "status.json", {"schema_version": 1, "status": "queued"}
        )
        record["experiments"][name] = experiment_id
    writer._write_json(writer.output_dir / f"{run_id}.json", record)
    return record


def run_suite(
    workspace: str | Path,
    suite_id: str,
    version: str,
    algorithms: list[dict[str, Any]],
    scenarios: list[str] | None = None,
) -> dict[str, Any]:
    """脚本模式运行场景集，每个场景使用与 Web 相同的核心执行器。"""
    from .runner.job import run_job

    record = create_run(workspace, suite_id, version, algorithms, scenarios)
    for identifier in record["experiments"].values():
        directory = Path(workspace) / "experiments" / identifier
        config = json.loads((directory / "config.json").read_text(encoding="utf-8"))
        run_job(config, str(directory), mode="script")
    return record


def leaderboard(
    workspace: str | Path, suite_id: str, version: str, column: int = 0, revision: str | None = None
) -> dict[str, Any]:
    """从完整实验汇总中读取指定点，按同一场景集版本排行。"""
    from .plugins import resolve_plugin

    root = Path(workspace)
    suite = load_suite(root, suite_id, version)
    if not 0 <= column < len(suite.leaderboard):
        raise ValueError("请选择有效排行榜列")
    columns = [
        {
            **c.model_dump(),
            "higher_is_better": resolve_plugin("metric", c.metric).higher_is_better,
            "metric_name": resolve_plugin("metric", c.metric).name,
            "unit": resolve_plugin("metric", c.metric).unit,
        }
        for c in suite.leaderboard
    ]
    rows: dict[str, dict[str, Any]] = {}
    revisions = []
    failures = []
    runs = []
    for path in (root / "benchmarks/runs").glob("*.json"):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
            if not all(
                key in record
                for key in (
                    "suite_id",
                    "suite_version",
                    "run_id",
                    "created_at",
                    "algorithms",
                    "experiments",
                )
            ):
                raise ValueError("评测记录缺少必要字段")
        except (OSError, ValueError) as exc:
            failures.append(f"评测记录 {path.name} 无法读取：{exc}")
            continue
        if record["suite_id"] == suite_id and record["suite_version"] == version:
            if record.get("suite_hash") != suite.digest:
                failures.append(f"{record['run_id']} 场景集哈希不符，已排除")
                continue
            runs.append(record)
    for record in sorted(runs, key=lambda r: (r["created_at"], r["run_id"])):
        revisions.append({"run_id": record["run_id"], "created_at": record["created_at"]})
        if revision is not None and record["run_id"] != revision:
            continue
        for algorithm in record["algorithms"]:
            label = algorithm.get("label") or algorithm["id"]
            parameters_hash = hashlib.sha256(
                json.dumps(algorithm.get("params", {}), sort_keys=True).encode("utf-8")
            ).hexdigest()[:12]
            key = algorithm["id"] + ":" + label + ":" + parameters_hash
            row = rows.setdefault(
                key,
                {
                    "key": key,
                    "id": algorithm["id"],
                    "label": label,
                    "algorithm": algorithm,
                    "values": [None] * len(columns),
                },
            )
            for index, spec in enumerate(suite.leaderboard):
                experiment_id = record["experiments"].get(spec.scenario)
                if not experiment_id:
                    continue
                directory = root / "experiments" / experiment_id
                try:
                    if directory.resolve().parent != (root / "experiments").resolve():
                        raise ValueError("实验记录引用了工作目录之外的路径")
                    status = json.loads((directory / "status.json").read_text(encoding="utf-8"))
                    if status.get("status") != "completed":
                        continue
                    summary = json.loads((directory / "summary.json").read_text(encoding="utf-8"))
                    meta = json.loads((directory / "meta.json").read_text(encoding="utf-8"))
                    actual = ExperimentConfig.model_validate_json(
                        (directory / "config.json").read_text(encoding="utf-8")
                    ).model_dump(mode="json")
                    scenario = next(s for s in suite.scenarios if s.name == spec.scenario)
                    expected = ExperimentConfig.model_validate(scenario.config).model_dump(
                        mode="json"
                    )
                    if any(
                        actual[key] != expected[key]
                        for key in ("scenario", "type", "trials", "sweep", "options", "metrics")
                    ):
                        raise ValueError("实验配置已偏离固定场景；修改后的结果不能进入本版本排行")
                    if (
                        not summary.get("complete")
                        or meta.get("benchmark", {}).get("suite_hash") != suite.digest
                    ):
                        continue
                    value = summary["points"][spec.at]["algorithms"][label]["metric_values"][
                        spec.metric
                    ]["value"]
                    provenance = meta.get("plugins", {}).get("algorithm/" + algorithm["id"], {})
                    row["values"][index] = {
                        "value": value if value is not None and math.isfinite(value) else None,
                        "experiment_id": experiment_id,
                        "run_id": record["run_id"],
                        "version": provenance.get("version"),
                        "commit": provenance.get("git", {}).get("commit"),
                        "dirty": provenance.get("git", {}).get("dirty", False),
                        "model": meta.get("models", {}).get(label, provenance.get("model")),
                    }
                except (OSError, ValueError, KeyError, IndexError) as exc:
                    failures.append(f"{experiment_id} 数据不完整：{exc}")
    direction = -1 if columns[column]["higher_is_better"] else 1

    def score(row: dict[str, Any]) -> float:
        cell = row["values"][column]
        return float(cell["value"]) * direction if cell and cell["value"] is not None else math.inf

    result = sorted(rows.values(), key=lambda r: (score(r), r["key"]))
    previous_score = math.inf
    current_rank = 0
    for rank, row in enumerate(result, 1):
        value = score(row)
        if value != previous_score:
            current_rank = rank
        row["rank"] = current_rank if math.isfinite(value) else None
        previous_score = value
        row["missing"] = sorted(
            {c.scenario for i, c in enumerate(suite.leaderboard) if row["values"][i] is None}
        )
    return {
        "suite_id": suite_id,
        "version": version,
        "columns": columns,
        "rows": result,
        "revisions": revisions,
        "failures": sorted(set(failures)),
    }
