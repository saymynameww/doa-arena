"""接口规范 14.5 的插件一致性检查，在 CLI 独立进程运行。"""

from __future__ import annotations

import gc
import json
import logging
import re
from dataclasses import replace
from pathlib import Path
from typing import Any

import numpy as np

from arena_api import Algorithm, Estimate, ModelAlgorithm, RunContext

from .config import ExperimentConfig
from .rng import RNGTree
from .runner.core import build_scene


def check_plugin(
    cls: type[Algorithm],
    parameters: dict[str, Any] | None = None,
    device: str = "cpu",
    workspace: Path | None = None,
) -> dict[str, Any]:
    """逐项检查插件，保持错误可诊断，合理性仅给警告。

    Args:
        cls: 被检查的算法类。
        parameters: 模型包等必需参数；普通算法默认使用默认参数。
        device: 实际检查设备。
        workspace: 模型相对路径的工作目录。
    """
    checks: list[dict[str, str]] = []

    def record(name: str, status: str, message: str) -> None:
        checks.append({"name": name, "status": status, "message": message})

    def validate_output(output: Any) -> None:
        if not isinstance(output, Estimate):
            raise ValueError("必须返回 Estimate")
        if output.angles.ndim != 1 or not np.isfinite(output.angles).all():
            raise ValueError("角度必须是一维有限数值数组")
        if (np.abs(output.angles) > 90).any():
            raise ValueError("角度超出 [-90, 90]")
        json.dumps(dict(output.info), allow_nan=False)
        if output.spectrum is not None:
            spectrum = output.spectrum
            if (
                not np.isfinite(spectrum.values).all()
                or (spectrum.values < 0).any()
                or not np.isfinite(spectrum.grid).all()
            ):
                raise ValueError("空间谱必须是有限非负值，网格必须有限")

    def equal(a: Estimate, b: Estimate) -> bool:
        tolerance = 1e-5 if device.startswith("cuda") else 0

        def same(x: Any, y: Any) -> bool:
            return np.shape(x) == np.shape(y) and bool(np.allclose(x, y, rtol=0, atol=tolerance))

        if not same(a.angles, b.angles):
            return False
        if (a.spectrum is None) != (b.spectrum is None):
            return False
        if a.spectrum is not None and b.spectrum is not None:
            return same(a.spectrum.grid, b.spectrum.grid) and same(
                a.spectrum.values, b.spectrum.values
            )
        return True

    # 这里只读取全局状态用于诊断，不使用它生成数据或重置插件的状态。
    before_random = np.random.get_state()  # noqa: NPY002 -- 接口 14.5 要求检查全局状态不变
    instances: list[Algorithm] = []
    try:
        if not re.fullmatch(r"[a-z][a-z0-9_]{1,39}", cls.id) or not cls.name or not cls.version:
            raise ValueError("请提供合法 id、名称和版本")
        if cls.api_version != 1:
            raise ValueError("api_version 必须为 1")
        schema = cls.Params.model_json_schema()
        if schema.get("required") and not issubclass(cls, ModelAlgorithm):
            raise ValueError("普通插件参数必须提供默认值")
        params = cls.Params.model_validate(parameters or {})
        record("定义", "passed", "类属性、参数与 JSON Schema 合法")
    except Exception as exc:
        record("定义", "failed", str(exc))
        return {"passed": False, "checks": checks}

    config = ExperimentConfig.model_validate(
        {
            "scenario": {
                "array": {"params": {"M": 16, "d": 0.5}},
                "snapshots": 200,
                "sources": {"K": 2, "snr_db": 20, "angles": {"values": [-10, 10]}},
            }
        }
    )
    scene, array = build_scene(config)
    tree = RNGTree(12345)
    observations = [scene.generate(tree.for_trial(i)) for i in range(20)]
    snapshots = [o.X.copy() for o in observations]
    ctx = RunContext(
        device, logging.getLogger("plugin-check"), True, workspace, tree.for_algorithm(cls.id, 0)
    )
    cuda = None
    baseline = 0
    if device.startswith("cuda"):
        import torch

        cuda = torch.cuda
        if not cuda.is_available():
            record("运行", "failed", "当前环境没有可用 CUDA，请用 --device cpu 或切换 GPU 环境")
            return {"passed": False, "checks": checks}
        baseline = cuda.memory_allocated()

    def make() -> Algorithm:
        algorithm = cls()
        instances.append(algorithm)
        issues = cls.check(params, array, 2)
        if any(i.level == "error" for i in issues):
            raise ValueError("；".join(i.message for i in issues if i.level == "error"))
        algorithm.load(params, ctx)
        algorithm.configure(params, array, ctx)
        return algorithm

    outputs: list[Estimate] = []
    try:
        first = make()
        for i, obs in enumerate(observations):
            output = first.estimate(obs, replace(ctx, rng=tree.for_algorithm(cls.id, i)))
            validate_output(output)
            outputs.append(output)
        record("默认参数运行与输出格式", "passed", "标准场景 20 次无异常，输出合法")
        rate = (
            sum(
                len(o.angles) == 2 and np.max(np.abs(np.sort(o.angles) - [-10, 10])) < 1
                for o in outputs
            )
            / 20
        )
        record(
            "合理性", "passed" if rate > 0.5 else "warning", f"成功率 {rate:.0%}，仅作适用性参考"
        )
        try:
            second = make()
            repeated = [
                second.estimate(o, replace(ctx, rng=tree.for_algorithm(cls.id, i)))
                for i, o in enumerate(observations)
            ]
            if not all(equal(a, b) for a, b in zip(outputs, repeated)):
                raise ValueError("同种子重复执行结果不同")
            record("确定性", "passed", "同种子结果一致")
        except Exception as exc:
            record("确定性", "failed", str(exc))
        if cls.capabilities.batch:
            try:
                batched = make().estimate_batch(
                    observations,
                    replace(
                        ctx, _batch_rngs=tuple(tree.for_algorithm(cls.id, i) for i in range(20))
                    ),
                )
                for output in batched:
                    validate_output(output)
                if len(batched) != 20 or not all(equal(a, b) for a, b in zip(outputs, batched)):
                    raise ValueError("批量与逐次结果不一致")
                record("批量一致", "passed", "逐次和批量输出一致")
            except Exception as exc:
                record("批量一致", "failed", str(exc))
        else:
            record("批量一致", "not_applicable", "插件未声明 batch")
    except Exception as exc:
        record("默认参数运行与输出格式", "failed", str(exc))
    finally:
        unchanged = all(
            np.array_equal(o.X, original) for o, original in zip(observations, snapshots)
        )
        record(
            "不修改输入",
            "passed" if unchanged else "failed",
            "输入未改变" if unchanged else "插件修改了共享观测数据",
        )
        try:
            for algorithm in instances:
                algorithm.close()
                algorithm.close()
            gc.collect()
            if cuda is not None:
                cuda.synchronize()
                if abs(cuda.memory_allocated() - baseline) > 50 * 1024**2:
                    raise ValueError("close 后显存与加载前相差超过 50 MB")
            record("资源释放", "passed", "close 可重复调用，显存检查通过或无需 CUDA")
        except Exception as exc:
            record("资源释放", "failed", str(exc))
        after_random = np.random.get_state()  # noqa: NPY002 -- 只读取状态，不生成随机数
        same_state = all(np.array_equal(a, b) for a, b in zip(before_random, after_random))
        record(
            "无全局随机状态",
            "passed" if same_state else "failed",
            "全局状态不变" if same_state else "插件改变了 numpy 全局随机状态",
        )
    return {"passed": not any(c["status"] == "failed" for c in checks), "checks": checks}


def check_registered(
    identifier: str, workspace: Path, parameters: dict[str, Any], device: str
) -> dict[str, Any]:
    """发现全局与工作目录登记的算法并检查。"""
    from .plugins import discover, resolve_algorithm

    sources = []
    for path in (Path("arena_settings.json"), workspace / "arena_workspace.json"):
        if path.exists():
            for source in json.loads(path.read_text(encoding="utf-8")).get("algorithm_sources", []):
                source = dict(source)
                if source.get("type") == "path":
                    for key in ("value", "import_root"):
                        if source.get(key) and not Path(source[key]).is_absolute():
                            source[key] = str((path.parent / source[key]).resolve())
                sources.append(source)
    catalog = discover(sources)
    entry = next((a for a in catalog["algorithms"] if a["id"] == identifier), None)
    if entry is None:
        raise ValueError("未找到算法，请检查登记来源和插件 id：" + identifier)
    return check_plugin(
        resolve_algorithm(identifier, entry["origin"]), parameters, device, workspace
    )
