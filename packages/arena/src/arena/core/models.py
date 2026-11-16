"""模型包导出、导入与训练范围检查，服务进程不加载权重。"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from arena_api import Algorithm, Issue, ModelAlgorithm, ModelMeta, ParamsModel

from .config import ScenarioConfig
from .datasets import _digest, distribution_values, read_config
from .runner.core import GENERATOR_VERSION


def parameters(cls: type[Algorithm], values: dict[str, Any], workspace: Path | None) -> ParamsModel:
    """仅在运行时解析模型相对路径，保持磁盘配置中的用户输入。"""
    values = dict(values)
    if issubclass(cls, ModelAlgorithm) and values.get("model"):
        path = Path(values["model"])
        if not path.is_absolute() and workspace is not None:
            path = workspace / path
        values["model"] = str(path.resolve())
    return cls.Params.model_validate(values)


def _training_code() -> dict[str, Any]:
    directory = Path(sys.argv[0]).resolve().parent

    def git(*args: str) -> str:
        result = subprocess.run(
            ["git", "-C", str(directory), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
        )
        return result.stdout.strip() if result.returncode == 0 else ""

    remote = git("remote", "get-url", "origin")
    if "://" in remote:
        parsed = urlsplit(remote)
        remote = urlunsplit((parsed.scheme, parsed.netloc.split("@")[-1], parsed.path, "", ""))
    return {
        "remote": remote or None,
        "commit": git("rev-parse", "HEAD") or None,
        "dirty": bool(git("status", "--porcelain")),
    }


def export(
    state_dict: Any,
    out_dir: str | Path,
    *,
    model_name: str,
    algorithm_id: str,
    array: dict[str, Any],
    input: str,
    output: dict[str, Any],
    hparams: dict[str, Any] | None = None,
    dataset: str | Path | dict[str, Any] | None = None,
    description: str = "",
    training: dict[str, Any] | None = None,
) -> Path:
    """在临时目录导出 state_dict 与元数据后重命名，不覆盖已有模型包。"""
    import torch

    import arena

    target = Path(out_dir).resolve()
    if target.exists():
        raise ValueError("模型输出目录已存在，请使用新的模型包目录")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", model_name):
        raise ValueError("模型名称只能包含 ASCII 字母、数字、下划线和连字符")
    target.parent.mkdir(parents=True, exist_ok=True)
    trained_on: dict[str, Any] = {"source": "external", "notes": "未提供 Arena 数据集配置"}
    if dataset is not None:
        if isinstance(dataset, str | Path) and Path(dataset).is_dir():
            manifest = json.loads((Path(dataset) / "dataset.json").read_text(encoding="utf-8"))
            trained_on = {
                "source": "arena",
                "dataset_id": manifest["id"],
                "dataset_config": manifest["config"],
                "generator_version": manifest["versions"]["generator"],
                "arena_version": manifest["versions"]["arena"],
            }
        else:
            trained_on = {
                "source": "arena",
                "dataset_id": None,
                "dataset_config": read_config(dataset).model_dump(mode="json"),
                "generator_version": GENERATOR_VERSION,
                "arena_version": arena.__version__,
            }
    temporary = Path(tempfile.mkdtemp(prefix=".model-", dir=target.parent))
    try:
        torch.save(state_dict, temporary / "model.pt")
        meta = ModelMeta.model_validate(
            {
                "model_name": model_name,
                "description": description,
                "algorithm_id": algorithm_id,
                "array": array,
                "input": input,
                "output": output,
                "hparams": hparams or {},
                "weights": {
                    "file": "model.pt",
                    "sha256": _digest(temporary / "model.pt"),
                    "format": "state_dict",
                },
                "trained_on": trained_on,
                "training": {
                    **(training or {}),
                    "code": _training_code(),
                    "torch": str(torch.__version__),
                    "gpu": torch.cuda.get_device_name() if torch.cuda.is_available() else None,
                },
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        meta.to_file(temporary / "model.json")
        temporary.rename(target)
    finally:
        if temporary.exists():
            # temporary 为本函数在已核实父目录下创建的临时目录。
            shutil.rmtree(temporary)
    return target


def import_package(source: str | Path, workspace: str | Path) -> Path:
    """安全导入目录或 zip，检查路径、名称和权重哈希，拒绝覆盖。"""
    source = Path(source).resolve()
    root = Path(workspace).resolve() / "models"
    if source.is_dir() and root.is_relative_to(source):
        raise ValueError("模型来源不能包含导入目标目录，请选择独立的模型包目录")
    root.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".import-", dir=root))
    try:
        if source.is_dir():
            for file in source.rglob("*"):
                if file.is_symlink() or not file.resolve().is_relative_to(source):
                    raise ValueError("模型包不能包含符号链接")
                if file.is_file():
                    dest = temporary / file.relative_to(source)
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(file, dest)
        else:
            with zipfile.ZipFile(source) as archive:
                for entry in archive.infolist():
                    name = entry.filename.replace("\\", "/")
                    dest = (temporary / name).resolve()
                    if (
                        not dest.is_relative_to(temporary)
                        or ":" in name
                        or (entry.external_attr >> 16) & 0o170000 == 0o120000
                    ):
                        raise ValueError("模型压缩包包含不安全路径或符号链接")
                    if entry.is_dir():
                        dest.mkdir(parents=True, exist_ok=True)
                    else:
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        with archive.open(entry) as stream, dest.open("wb") as output:
                            shutil.copyfileobj(stream, output)
        meta_files = list(temporary.rglob("model.json"))
        if len(meta_files) != 1:
            raise ValueError("模型包必须恰好包含一个 model.json")
        meta = ModelMeta.from_file(meta_files[0])
        meta.verify_weights()
        target = root / meta.model_name
        if target.exists():
            raise ValueError("同名模型包已存在，请更换模型名称后重新导出")
        from .storage.writer import ResultWriter

        ResultWriter(meta.path)._write_json(
            meta.path / "import.json",
            {"imported_at": datetime.now(timezone.utc).isoformat(), "weights_verified": True},
        )
        meta.path.rename(target)
        return target
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)


def inspect_package(source: str | Path) -> dict[str, Any]:
    """在临时工作目录中完成与正式导入相同的检查，不修改实际工作目录。"""
    with tempfile.TemporaryDirectory(prefix="arena-model-check-") as temporary:
        path = import_package(source, temporary)
        meta = ModelMeta.from_file(path)
        return {
            "metadata": meta.model_dump(mode="json"),
            "checks": ["元数据结构有效", "权重 SHA256 校验通过"],
            "warnings": ["信号生成器版本与当前版本不同，评测时将提示"]
            if meta.generator_version not in (None, GENERATOR_VERSION)
            else [],
        }


def training_issues(
    meta: ModelMeta, scenario: ScenarioConfig, commit: str | None = None
) -> list[Issue]:
    """数据格式 6.3：逐场景检查训练范围，所有偏离只产生警告。"""
    issues = []
    if meta.generator_version is not None and meta.generator_version != GENERATOR_VERSION:
        issues.append(
            Issue(
                "warning",
                f"信号生成器版本不一致：训练 {meta.generator_version}，评测 {GENERATOR_VERSION}",
            )
        )
    trained_commit = meta.training.get("code", {}).get("commit")
    if commit and trained_commit and commit != trained_commit:
        issues.append(Issue("warning", "训练代码 commit 与当前评测插件不同，请核查模型与代码版本"))
    if meta.trained_on.get("source") != "arena":
        return issues
    trained = meta.trained_on["dataset_config"]["scenario"]
    sources = trained.get("sources", {})

    def compare(
        label: str, actual: float, support: Any, *, tolerance: float = 0, discrete: bool = False
    ) -> None:
        values = distribution_values(support)
        outside = actual < min(values) - tolerance or actual > max(values) + tolerance
        if discrete and isinstance(support, dict) and "choice" in support:
            outside = actual not in values
        if outside:
            issues.append(
                Issue("warning", f"超出训练范围：{label} = {actual:g}，训练范围 {values}")
            )

    counts = (
        [scenario.sources.K] if isinstance(scenario.sources.K, int) else scenario.sources.K.values
    )
    for count in counts:
        compare("K", count, sources.get("K", 2), discrete=True)
    snrs = scenario.sources.snr_db
    for snr in snrs if isinstance(snrs, list) else [snrs]:
        compare("SNR (dB)", snr, sources.get("snr_db", 10), tolerance=0.01)
    compare("快拍数", scenario.snapshots, trained.get("snapshots", 100))
    angles = sources.get("angles", {"mode": "fixed", "values": [-10, 10]})
    test_angles = scenario.sources.angles
    if angles.get("mode") == "fixed":
        if test_angles.mode != "fixed" or test_angles.values != angles.get("values"):
            issues.append(Issue("warning", "超出训练范围：测试角度与训练固定角度不同"))
    else:
        bounds = angles.get("range_deg", [angles.get("min", -60), angles.get("max", 60)])
        if test_angles.mode == "fixed":
            actual_angles = test_angles.values or []
        elif test_angles.mode == "random":
            actual_angles = list(test_angles.range_deg or [])
        else:
            actual_angles = [
                test_angles.center - (test_angles.delta or 0) / 2,
                test_angles.center + (test_angles.delta or 0) / 2,
            ]
        for angle in actual_angles:
            compare("角度 (°)", angle, {"uniform": bounds})
    correlation = sources.get("correlation", {"mode": "none"})
    if scenario.sources.correlation.mode != correlation.get("mode", "none"):
        issues.append(Issue("warning", "超出训练范围：信源相关性模式不同"))
    elif scenario.sources.correlation.mode == "partial":
        compare(
            "相关系数幅度",
            scenario.sources.correlation.rho_mag or 0,
            correlation.get("rho", {}).get("mag", correlation.get("rho_mag", 0)),
        )
    impairments = {i["type"]: i for i in trained.get("impairments", []) if i.get("enabled", True)}
    for impairment in scenario.impairments:
        if not impairment.enabled:
            continue
        if impairment.type not in impairments:
            issues.append(Issue("warning", f"超出训练范围：训练中未包含误差 {impairment.type}"))
        else:
            from .datasets import _realize
            from .plugins import resolve_plugin

            cls = resolve_plugin("impairment", impairment.type, impairment.origin)
            raw = impairments[impairment.type].get("params", {})
            support = {
                **cls.Params.model_validate(_realize(raw, 0, 0)).model_dump(mode="json"),
                **raw,
            }
            actual = cls.Params.model_validate(impairment.params).model_dump(mode="json")

            def compare_tree(value: Any, reference: Any, label: str) -> None:
                if isinstance(value, bool) or value is None or reference is None:
                    return
                if isinstance(value, int | float):
                    compare(label, value, reference)
                elif isinstance(value, dict) and isinstance(reference, dict):
                    for key, child in value.items():
                        if key in reference:
                            compare_tree(child, reference[key], label + "." + key)
                elif isinstance(value, list) and isinstance(reference, list):
                    if len(value) != len(reference):
                        issues.append(Issue("warning", f"超出训练范围：{label} 长度不同"))
                    for index, (child, ref) in enumerate(zip(value, reference)):
                        compare_tree(child, ref, f"{label}[{index}]")

            compare_tree(actual, support, impairment.type)
    return issues
