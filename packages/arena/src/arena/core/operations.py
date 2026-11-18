"""服务调用的隔离核心操作，标准输出仅返回 JSON。"""

from __future__ import annotations

import contextlib
import io
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


def invoke(operation: str, payload: dict[str, Any]) -> dict[str, Any]:
    """在独立进程校验、重算或绘图，服务进程不加载第三方算法。"""
    process = subprocess.run(
        [sys.executable, "-m", "arena.core.operations"],
        input=json.dumps({"operation": operation, "payload": payload}),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
    )
    if process.returncode:
        raise ValueError(f"核心操作失败：{process.stderr[-2000:]}")
    response = json.loads(process.stdout)
    if "error" in response:
        raise ValueError(response["error"])
    return dict(response)


def execute(operation: str, payload: dict[str, Any]) -> dict[str, Any]:
    """执行子进程收到的白名单操作。"""
    from .config import ExperimentConfig

    if operation == "compare_export":
        from .figures.compare import export_comparison

        return export_comparison(payload)

    if operation == "environment":
        import importlib.metadata
        import platform

        import arena
        import arena_api

        from .runner.core import GENERATOR_VERSION

        info: dict[str, Any] = {
            "Arena": arena.__version__,
            "API": arena_api.__version__,
            "数据生成器": GENERATOR_VERSION,
            "Python": platform.python_version(),
            "cuda_available": False,
        }
        for name in ("numpy", "scipy", "torch"):
            try:
                info[name] = importlib.metadata.version(name)
            except importlib.metadata.PackageNotFoundError:
                info[name] = "未安装"
        try:
            commit = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=Path(__file__).parent,
                capture_output=True,
                text=True,
                timeout=5,
            )
            info["commit"] = commit.stdout.strip() or "未记录"
        except (OSError, subprocess.TimeoutExpired):
            info["commit"] = "未记录"
        if info["torch"] != "未安装":
            try:
                import torch

                info["CUDA"] = torch.version.cuda or "CPU 构建"
                info["cuda_available"] = torch.cuda.is_available()
                info["GPU"] = (
                    torch.cuda.get_device_name(0) if torch.cuda.is_available() else "不可用"
                )
            except Exception as exc:
                raise RuntimeError(f"PyTorch/CUDA 探测失败：{exc}") from exc
        else:
            info["GPU"] = "未安装学习依赖"
        return info

    if operation.startswith("benchmark_"):
        from .benchmark import create_run, leaderboard, list_suites, save_suite

        workspace = payload["workspace"]
        if operation == "benchmark_suites":
            return {"suites": list_suites(workspace)}
        if operation == "benchmark_save":
            return save_suite(payload["suite"], workspace)
        if operation == "benchmark_create":
            return create_run(
                workspace,
                payload["suite_id"],
                payload["version"],
                payload["algorithms"],
                payload.get("scenarios"),
            )
        if operation == "benchmark_leaderboard":
            return leaderboard(
                workspace,
                payload["suite_id"],
                payload["version"],
                payload.get("column", 0),
                payload.get("revision"),
            )

    if operation == "inspect_model":
        from .models import inspect_package

        return inspect_package(payload["source"])

    if operation == "import_model":
        from arena_api import ModelMeta

        from .models import import_package

        path = import_package(payload["source"], payload["workspace"])
        meta = ModelMeta.from_file(path)
        return {
            "path": str(path),
            "name": meta.model_name,
            "algorithm_id": meta.algorithm_id,
            "metadata": meta.model_dump(mode="json"),
        }

    if operation == "preview":
        from .exploration import preview_scenario

        return preview_scenario(ExperimentConfig.model_validate(payload["config"]).scenario)
    if operation == "validate":
        from .validation import validate_configuration

        config = ExperimentConfig.model_validate(payload["config"])
        config._workspace = Path(payload["workspace"]) if payload.get("workspace") else None
        return {"valid": True, "issues": validate_configuration(config)}
    directory = Path(payload["directory"])
    if operation == "details":
        from .figures.details import result_details
        from .storage.reader import read_result

        details = result_details(read_result(directory))
        errors_path = directory / "errors.json"
        details["error_groups"] = (
            json.loads(errors_path.read_text(encoding="utf-8")).get("algorithms", [])
            if errors_path.exists()
            else []
        )
        return details
    if operation == "export":
        from .export.service import export_result

        path = export_result(
            directory,
            payload["format"],
            payload.get("metric", "rmse"),
            payload.get("chart"),
            payload.get("style", "web"),
            payload.get("log", False),
            payload.get("style_options"),
        )
        return {"path": str(path)}
    if operation == "finalize":
        from .storage.finalize import finalize_directory

        result = finalize_directory(directory)
        return {"metadata": result.metadata}
    if operation == "recompute":
        from .facade import recompute_metrics

        result = recompute_metrics(directory, payload["metrics"])
        return {"config": result.config, "metadata": result.metadata}
    if operation == "charts":
        from .figures.presentation import build_figures
        from .storage.reader import read_result

        return {
            "charts": [
                {"title": title, **json.loads(figure.to_json())}
                for title, figure in build_figures(read_result(directory)).items()
            ]
        }
    raise ValueError("未知核心操作")


if __name__ == "__main__":
    request = json.loads(sys.stdin.read())
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            response = execute(request["operation"], request["payload"])
    except Exception as exc:
        response = {"error": str(exc)}
    print(json.dumps(response, ensure_ascii=True))
