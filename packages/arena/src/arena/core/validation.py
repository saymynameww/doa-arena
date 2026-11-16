"""所有入口共享的扫描点静态兼容性校验。"""

from dataclasses import asdict
from typing import Any

from arena_api import Algorithm

from .config import ExperimentConfig


def validate_configuration(
    config: ExperimentConfig, classes: dict[str, type[Algorithm]] | None = None
) -> list[dict[str, Any]]:
    """检查所有扫描点及随机信源数候选，错误阻止运行，警告保留给界面。"""
    from .plugins import resolve_algorithm
    from .runner.core import build_scene, expand_point

    config.validate_experiment()
    issues = []
    for index, value in enumerate(
        config.sweep.values if config.type == "sweep" and config.sweep else [None]
    ):
        point = expand_point(config, value)
        _, array = build_scene(point)
        source_count = point.scenario.sources.K
        counts = [source_count] if isinstance(source_count, int) else source_count.values
        for item in point.algorithms:
            if not item.enabled:
                continue
            cls = (classes or {}).get(item.get_label()) or resolve_algorithm(item.id, item.origin)
            params = cls.Params(**item.params)
            for count in counts:
                for issue in cls.check(params, array, count) or []:
                    issues.append({**asdict(issue), "algorithm": item.get_label(), "point": index})
    errors = [issue["message"] for issue in issues if issue["level"] == "error"]
    if errors:
        raise ValueError("；".join(dict.fromkeys(errors)))
    return issues
