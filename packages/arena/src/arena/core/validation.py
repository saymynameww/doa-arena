"""所有入口共享的扫描点静态兼容性校验。"""

from dataclasses import asdict
from typing import Any

from arena_api import Algorithm, Issue, ModelAlgorithm, ModelMeta

from .config import ExperimentConfig
from .rng import RNGTree


def validate_configuration(
    config: ExperimentConfig, classes: dict[str, type[Algorithm]] | None = None
) -> list[dict[str, Any]]:
    """检查所有扫描点及随机信源数候选，错误阻止运行，警告保留给界面。"""
    from .plugins import resolve_algorithm, resolve_plugin
    from .runner.core import build_scene, expand_point

    config.validate_experiment()
    issues = []
    for index, value in enumerate(
        config.sweep.values if config.type == "sweep" and config.sweep else [None]
    ):
        point = expand_point(config, value)
        scene, array = build_scene(point)
        array = scene.algorithm_array(RNGTree(point.scenario.seed).for_trial(0))
        array_cls = resolve_plugin("array", point.scenario.array.type, point.scenario.array.origin)
        for issue in array_cls.check(array_cls.Params(**point.scenario.array.params)):
            issues.append({**asdict(issue), "point": index, "component": "array"})
        for entry in point.scenario.impairments:
            if not entry.enabled:
                continue
            imp_cls = resolve_plugin("impairment", entry.type, entry.origin)
            for issue in imp_cls.check(imp_cls.Params(**entry.params), array.M):
                issues.append({**asdict(issue), "point": index, "component": entry.type})
        for name in point.metrics.include:
            if name == "crb":
                continue
            name = "resolution_prob" if name == "resolution" else name
            metric = resolve_plugin("metric", name, point.metrics.origins.get(name))
            metric.Params(**point.metrics.params.model_dump().get(name, {}))
        source_count = point.scenario.sources.K
        counts = [source_count] if isinstance(source_count, int) else source_count.values
        for item in point.algorithms:
            if not item.enabled:
                continue
            cls = (classes or {}).get(item.get_label()) or resolve_algorithm(item.id, item.origin)
            from .models import parameters

            params = parameters(cls, point.search_parameters(cls, item.params), config._workspace)
            warnings = []
            if issubclass(cls, ModelAlgorithm):
                from .models import training_issues

                try:
                    model = ModelMeta.from_file(getattr(params, "model"))
                    warnings.extend(
                        training_issues(model, point.scenario, (item.origin or {}).get("commit"))
                    )
                except (OSError, ValueError):
                    # 由 check 生成统一的、可定位到算法卡片的错误。
                    pass
            if point.scenario.snapshots < array.M:
                warnings.append(Issue("warning", "快拍数小于阵元数，样本协方差可能奇异"))
            coherent = point.scenario.sources.correlation.mode == "coherent"
            if coherent and (
                cls.capabilities.coherent == "no"
                or (
                    cls.capabilities.coherent == "with_smoothing"
                    and getattr(params, "smoothing", "none") == "none"
                )
            ):
                warnings.append(Issue("warning", "相干信源下没有开启空间平滑，估计可能失效"))
            for warning in warnings:
                issues.append({**asdict(warning), "algorithm": item.get_label(), "point": index})
            for count in counts:
                for issue in cls.check(params, array, count) or []:
                    issues.append({**asdict(issue), "algorithm": item.get_label(), "point": index})
    errors = [issue["message"] for issue in issues if issue["level"] == "error"]
    if errors:
        raise ValueError("；".join(dict.fromkeys(errors)))
    return issues
