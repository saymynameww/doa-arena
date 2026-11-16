"""插件发现、独立进程探测与来源记录（接口规范第 10 章）。"""

from __future__ import annotations

import hashlib
import importlib.metadata
import importlib.util
import inspect
import json
import re
import subprocess
import sys
import traceback
import types
from dataclasses import asdict
from pathlib import Path
from typing import Any

from arena_api import Algorithm


def load_module(path: Path, import_root: Path | None = None) -> types.ModuleType:
    """按独立包加载入口，支持相对导入且不执行训练脚本。"""
    path = path.resolve()
    root = import_root or path.parent.parent.parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    package = "arena_ext_" + hashlib.sha256(str(path.parent).encode()).hexdigest()[:16]
    parent = types.ModuleType(package)
    parent.__path__ = [str(path.parent)]
    sys.modules[package] = parent
    name = package + "." + path.stem
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ValueError(f"无法加载插件入口 {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def provenance(cls: type[Algorithm]) -> dict[str, Any]:
    """记录实际代码、Git 状态和未提交补丁，哈希包含插件目录代码。"""
    file = Path(inspect.getfile(cls)).resolve()
    digest = hashlib.sha256()
    for item in sorted(file.parent.rglob("*.py")):
        digest.update(item.relative_to(file.parent).as_posix().encode())
        digest.update(item.read_bytes())
    result: dict[str, Any] = {
        "file": str(file),
        "qualname": cls.__name__,
        "module": cls.__module__,
        "version": cls.version,
        "code_hash": digest.hexdigest(),
    }

    def git(*args: str) -> str:
        return (
            subprocess.check_output(
                ["git", "-C", str(file.parent), *args], stderr=subprocess.DEVNULL
            )
            .decode("utf-8", errors="replace")
            .strip()
        )

    try:
        result.update(
            commit=git("rev-parse", "HEAD"),
            dirty=bool(git("status", "--porcelain")),
            patch=git("diff", "HEAD"),
        )
    except (subprocess.SubprocessError, OSError):
        result.update(commit=None, dirty=False, patch="")
    return result


def builtin_classes() -> dict[str, type[Algorithm]]:
    """取得内置算法，外部插件走同一生命周期。"""
    from .algorithms import CBF, ESPRIT, MUSIC, MVDR, RootMUSIC

    return {cls.id: cls for cls in (CBF, MVDR, MUSIC, RootMUSIC, ESPRIT)}


def discover(sources: list[dict[str, Any]]) -> dict[str, Any]:
    """扫描入口并隔离单个插件错误；外部冲突双方均不注册。"""
    classes = builtin_classes()
    records: dict[str, dict[str, Any]] = {}
    failures: list[dict[str, Any]] = []
    conflicts: set[str] = set()

    def register(cls: type[Algorithm], source: dict[str, Any] | None = None) -> None:
        if not re.fullmatch(r"[a-z][a-z0-9_]{1,39}", cls.id):
            raise ValueError("插件 id 必须为 2–40 位小写字母、数字或下划线")
        if not cls.name or not cls.version or cls.api_version != 1:
            raise ValueError("插件缺少名称、版本，或 api_version 不兼容")
        schema = cls.Params.model_json_schema()
        if schema.get("required") and cls.category != "learning":
            raise ValueError("插件参数必须提供默认值：" + ", ".join(schema["required"]))
        key = cls.id
        if source and key in classes:
            key = f"{source.get('name') or Path(source['value']).name}/{key}"
        if key in records or key in conflicts:
            previous = records.pop(key, None)
            conflicts.add(key)
            raise ValueError(f"外部插件 id 冲突，双方停用：{key}，原入口 {previous}")
        origin = provenance(cls)
        if source:
            origin["import_root"] = source.get("import_root") or str(Path(source["value"]).parent)
        records[key] = {
            "id": key,
            "name": cls.name,
            "version": cls.version,
            "type": "external" if source else "builtin",
            "description": cls.description,
            "category": cls.category,
            "schema": schema,
            "params": schema.get("properties", {}),
            "capabilities": asdict(cls.capabilities),
            "origin": origin,
        }

    for cls in classes.values():
        register(cls)
    for source in sources:
        try:
            if source.get("type", "path") == "package":
                entries = importlib.metadata.entry_points(group="doa_arena.plugins")
                modules = [
                    ep.load()
                    for ep in entries
                    if not source.get("value") or ep.name == source["value"]
                ]
            else:
                root = Path(source["value"]).expanduser().resolve()
                if not root.is_dir():
                    raise ValueError(f"算法来源目录不存在：{root}")
                modules = []
                for child in sorted(root.iterdir()):
                    if child.name.startswith(("_", ".")):
                        continue
                    entry = child / "arena_plugin.py" if child.is_dir() else child
                    if entry.suffix != ".py" or not entry.is_file():
                        continue
                    try:
                        modules.append(
                            load_module(entry, Path(source.get("import_root") or root.parent))
                        )
                    except Exception as exc:
                        failures.append(
                            {
                                "path": str(entry),
                                "message": str(exc),
                                "traceback": traceback.format_exc(),
                            }
                        )
            for module in modules:
                for name, cls in vars(module).items():
                    if (
                        name.startswith("_")
                        or not inspect.isclass(cls)
                        or cls.__module__ != module.__name__
                    ):
                        continue
                    if issubclass(cls, Algorithm) and not inspect.isabstract(cls):
                        try:
                            register(cls, source)
                        except Exception as exc:
                            failures.append(
                                {
                                    "path": str(inspect.getfile(cls)),
                                    "message": str(exc),
                                    "traceback": traceback.format_exc(),
                                }
                            )
        except Exception as exc:
            failures.append(
                {
                    "path": source.get("value", ""),
                    "message": str(exc),
                    "traceback": traceback.format_exc(),
                }
            )
    return {"algorithms": list(records.values()), "failures": failures, "sources": sources}


def resolve_algorithm(identifier: str, origin: dict[str, Any] | None = None) -> type[Algorithm]:
    """在实验进程内解析已登记或脚本来源的类。"""
    builtins = builtin_classes()
    if identifier in builtins and not origin:
        return builtins[identifier]
    if origin and origin.get("file"):
        module = load_module(
            Path(origin["file"]), Path(origin["import_root"]) if origin.get("import_root") else None
        )
        return getattr(module, origin["qualname"])
    raise ValueError(f"未找到算法 {identifier}，请在设置中登记来源并刷新")


def probe(sources: list[dict[str, Any]]) -> dict[str, Any]:
    """服务进程仅接收 JSON 元数据，第三方插件导入发生在子进程。"""
    result = subprocess.run(
        [sys.executable, "-m", "arena.core.plugins"],
        input=json.dumps(sources),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )
    if result.returncode:
        raise ValueError(f"插件探测失败：{result.stderr}")
    return json.loads(result.stdout)


if __name__ == "__main__":
    import contextlib
    import io

    sources = json.loads(sys.stdin.read())
    with contextlib.redirect_stdout(io.StringIO()):
        metadata = discover(sources)
    print(json.dumps(metadata, ensure_ascii=True))
