"""按试验块执行的 spawn 工作进程，插件资源在进程内复用。"""

from __future__ import annotations

import json
import logging
from multiprocessing.util import Finalize
from typing import Any

from arena_api import Algorithm, RunContext

from ..config import ExperimentConfig
from ..rng import RNGTree
from .results import TrialResult

_instances: dict[str, Algorithm] = {}
_configured: str | None = None
_errors: dict[str, str] = {}
_active: dict[str, Algorithm] = {}
_finalizer: Any = None


def close_worker() -> None:
    """在工作进程退出时释放所有插件资源。"""
    for instance in _instances.values():
        try:
            instance.close()
        except Exception:
            logging.getLogger(__name__).exception("工作进程释放算法资源失败")


def execute_chunk(
    document: dict[str, Any],
    point_index: int,
    indices: list[int],
    classes: dict[str, type[Algorithm]] | None = None,
) -> list[TrialResult]:
    """使用原始试验序号派生随机数，进程调度顺序不影响结果。"""
    from .core import (
        _load_algorithms,
        _warmup_algorithms,
        build_scene,
        needs_spectrum,
        run_trial,
        save_spectrum,
    )

    global _configured, _active, _finalizer
    if _finalizer is None:
        _finalizer = Finalize(None, close_worker, exitpriority=10)
    config = ExperimentConfig.model_validate(document)
    scene, array = build_scene(config)
    signature = json.dumps(document, sort_keys=True)
    if signature != _configured:
        _errors.clear()
        _active = _load_algorithms(config, array, _instances, _errors, classes)
        if config.options.warmup:
            _warmup_algorithms(scene, _active, RNGTree(config.scenario.seed))
        _configured = signature
    ctx = RunContext(
        "cpu",
        logging.getLogger(__name__),
        needs_spectrum(config),
        None,
        RNGTree(config.scenario.seed).for_scenario(),
    )
    from .batch import execute_batches

    batch_cache = execute_batches(config, point_index, indices, _active, ctx)
    results = []
    for trial_index in indices:
        random_index = (
            trial_index
            if config.options.common_random_numbers
            else point_index * config.trials + trial_index
        )
        scene, _ = build_scene(config, random_index)
        result = run_trial(
            trial_index,
            scene,
            _active,
            RNGTree(config.scenario.seed).for_trial(random_index),
            ctx,
            config.options.source_count,
            config.type == "single" and config.options.save_observations == "auto",
            batch_cache.get(trial_index),
            save_spectrum(config),
        )
        result.errors.update(_errors)
        results.append(result)
    return results
