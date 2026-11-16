"""实验版本和运行环境记录，不导入 torch，不收集主机名或用户名。"""

import importlib.metadata
import platform
from typing import Any

from arena_api import Algorithm

from ..config import ExperimentConfig


def capture(config: ExperimentConfig, instances: dict[str, Algorithm]) -> dict[str, Any]:
    """采集本次实际加载插件的版本和外部代码来源。"""
    import arena
    import arena_api

    from ..plugins import provenance
    from ..runner.core import GENERATOR_VERSION

    environment: dict[str, Any] = {
        "os": platform.platform(),
        "python": platform.python_version(),
        "cpu": platform.processor(),
        "workers": config.options.workers,
    }
    for name in ("numpy", "scipy", "torch"):
        try:
            environment[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            environment[name] = None
    plugins = {}
    patches = {}
    for item in config.algorithms:
        instance = instances.get(item.get_label())
        if instance is None:
            continue
        cls = type(instance)
        record: dict[str, Any] = {
            "name": cls.name,
            "version": cls.version,
            "api_version": cls.api_version,
            "source": {"type": "builtin", "location": cls.__module__},
        }
        if not cls.__module__.startswith("arena.core."):
            source = provenance(cls)
            record["source"] = {
                "type": "path" if item.origin else "script",
                "location": source["file"],
                "code_sha256": source["code_hash"],
            }
            if source.get("commit"):
                record["git"] = {"commit": source["commit"], "dirty": source["dirty"]}
                if source.get("patch"):
                    filename = cls.id + ".diff"
                    record["git"]["patch"] = "algorithm_patches/" + filename
                    patches[filename] = source["patch"]
        plugins["algorithm/" + item.id] = record
    return {
        "versions": {
            "arena": arena.__version__,
            "arena_api": arena_api.__version__,
            "generator_version": GENERATOR_VERSION,
        },
        "environment": environment,
        "plugins": plugins,
        "_patches": patches,
    }
