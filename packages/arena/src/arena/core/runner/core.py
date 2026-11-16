"""Runner 核心实现。"""

from __future__ import annotations

import json
import logging
import multiprocessing as mp
import time
import traceback
from collections.abc import Callable
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from dataclasses import replace

import numpy as np

from arena_api import Algorithm, ArrayDescriptor, Estimate, RunContext

from ..config import ExperimentConfig
from ..rng import RNGTree, TrialRNG
from ..scenario import ImpairmentInstance, ScenarioConfig, ScenarioGenerator
from ..signals import CorrelationMatrix
from .results import ExperimentResult, SweepPointResult, TrialResult

logger = logging.getLogger(__name__)


def save_spectrum(config: ExperimentConfig) -> bool:
    """判断谱数组是否需要持久化。"""
    return config.options.save_spectra == "all" or (
        config.options.save_spectra == "auto" and config.type == "single"
    )


def needs_spectrum(config: ExperimentConfig) -> bool:
    """谱谷判据需要瞬时谱，但不要求保存全部试验的谱数组。"""
    return (
        save_spectrum(config)
        or config.metrics.params.model_dump().get("resolution_prob", {}).get("criterion")
        == "spectrum"
    )


def run_trial(
    trial_idx: int,
    scenario_gen: ScenarioGenerator,
    algorithms: dict[str, Algorithm],
    trial_rng: TrialRNG,
    ctx: RunContext,
    source_count: str = "true",
    save_observation: bool = False,
    batch_results: dict[str, tuple[Estimate | Exception, float]] | None = None,
    retain_spectrum: bool = True,
) -> TrialResult:
    """运行单次试验。

    Args:
        trial_idx: 试验索引
        scenario_gen: 场景生成器
        algorithms: 算法字典 {label: algorithm}
        trial_rng: 试验随机数管理器
        ctx: 运行上下文
        source_count: 信源数提供方式
        save_observation: 是否保留接收数据
        batch_results: 已执行的批量结果及均摊耗时
        retain_spectrum: 是否保存空间谱；谱谷判据可只保留判断结果

    Returns:
        试验结果
    """
    # 生成观测数据
    obs = scenario_gen.generate(trial_rng)
    if source_count != "true":
        from .source_count import estimate_source_count

        obs = replace(obs, K=estimate_source_count(obs, source_count))

    trial_array = scenario_gen.algorithm_array(trial_rng)
    # 运行所有算法
    estimates = {}
    errors = {}
    times_ms = {}
    error_details = {}

    for label, algo in algorithms.items():
        try:
            if not np.array_equal(
                getattr(algo, "_current_mask", np.array([])), trial_array.element_mask
            ):
                params = algo.Params(**algo._loaded_parameters)
                problems = algo.check(params, trial_array, obs.K)
                if any(issue.level == "error" for issue in problems):
                    raise ValueError(
                        "；".join(issue.message for issue in problems if issue.level == "error")
                    )
                algo.configure(params, trial_array, ctx)
                algo._current_mask = trial_array.element_mask
            # 计时
            algo_ctx = replace(ctx, rng=trial_rng.for_impairment("algorithm:" + label, "random"))
            if batch_results and label in batch_results:
                output, elapsed = batch_results[label]
                if isinstance(output, Exception):
                    raise output
                est = output
            else:
                start = time.perf_counter()
                est = algo.estimate(obs, algo_ctx)
                if algo.capabilities.uses_gpu and getattr(algo, "device_str", "cuda").startswith(
                    "cuda"
                ):
                    import torch

                    if torch.cuda.is_available():
                        torch.cuda.synchronize(getattr(algo, "device_str", None))
                elapsed = (time.perf_counter() - start) * 1000
            if not isinstance(est, Estimate):
                raise ValueError("bad_output：算法必须返回 Estimate")
            if not np.all(np.isfinite(est.angles)):
                raise ValueError("nan_output：估计角度含 NaN 或 Inf")
            if np.any(np.abs(est.angles) > 90):
                raise ValueError("out_of_range：估计角度超出 [-90,90]")
            try:
                json.dumps(dict(est.info), allow_nan=False)
            except (TypeError, ValueError):
                est = replace(est, info={"warning": "算法 info 不是有效 JSON，已丢弃"})
            if est.spectrum is not None and (
                not np.all(np.isfinite(est.spectrum.values)) or np.any(est.spectrum.values < 0)
            ):
                est = replace(est, spectrum=None, info={**est.info, "warning": "无效空间谱已丢弃"})

            if est.spectrum is not None and len(scenario_gen.config.angles) == 2:
                resolved = False
                if len(est.angles) == 2:
                    lower, upper = np.sort(est.angles)
                    grid, values = est.spectrum.grid, est.spectrum.values
                    between = values[(grid > lower) & (grid < upper)]
                    peaks = np.interp([lower, upper], grid, values)
                    resolved = bool(len(between) and np.min(between) < np.mean(peaks))
                est = replace(est, info={**est.info, "resolved_by_spectrum": resolved})
            if not retain_spectrum:
                est = replace(est, spectrum=None)
            estimates[label] = est
            times_ms[label] = elapsed

        except Exception as e:
            logger.error(f"算法 {label} 在试验 {trial_idx} 出错: {e}")
            errors[label] = str(e)
            error_details[label] = {"type": type(e).__name__, "traceback": traceback.format_exc()}

    return TrialResult(
        trial_idx=trial_idx,
        estimates=estimates,
        errors=errors,
        times_ms=times_ms,
        truth_angles=scenario_gen.config.angles.copy(),
        observation=obs.X if save_observation else None,
        source_count=obs.K,
        error_details=error_details,
    )


def run_experiment(
    config: ExperimentConfig,
    progress_callback: Callable[[int, int, int, int], None] | None = None,
    cancel_callback: Callable[[], bool] | None = None,
    checkpoint_callback: Callable[[ExperimentResult], None] | None = None,
    algorithm_classes: dict[str, type[Algorithm]] | None = None,
) -> ExperimentResult:
    """运行实验。

    Args:
        config: 实验配置
        progress_callback: 可选进度回调，参数为已完成试验数、总试验数、当前扫描点和扫描点总数
        cancel_callback: 返回是否请求取消，每次试验前检查
        checkpoint_callback: 接收已完成试验的检查点，供持久化恢复使用
        algorithm_classes: 脚本直接传入的算法类，按实例标签查找

    Returns:
        实验结果
    """
    start_time = time.time()

    # 验证配置
    config.validate_experiment()
    from ..validation import validate_configuration

    validation_issues = validate_configuration(config, algorithm_classes)

    # 创建随机数树
    rng_tree = RNGTree(config.scenario.seed)

    # 每个扫描点重新构建场景，避免只改坐标而未改变观测数据。
    # 确定扫描点
    sweep_values: list[float | None]
    if config.type == "sweep" and config.sweep:
        sweep_values = list(config.sweep.values)
    else:
        sweep_values = [None]  # 单点

    # 运行所有扫描点
    points: list[SweepPointResult] = []

    instances: dict[str, Algorithm] = {}
    setup_errors: dict[str, str] = {}
    cancelled = False
    total_points = len(sweep_values)
    total_trials = total_points * config.trials

    pool = (
        ProcessPoolExecutor(max_workers=config.options.workers, mp_context=mp.get_context("spawn"))
        if config.options.workers > 1
        else None
    )
    try:
        for point_idx, sweep_val in enumerate(sweep_values):
            logger.info(f"运行扫描点 {point_idx + 1}/{len(sweep_values)}")

            setup_errors.clear()
            point_config = expand_point(config, sweep_val)
            scene, array = build_scene(point_config)
            algorithms = _load_algorithms(
                point_config, array, instances, setup_errors, algorithm_classes
            )
            instances.update(algorithms)
            if config.options.warmup:
                _warmup_algorithms(scene, algorithms, RNGTree(config.scenario.seed))
            ctx = RunContext(
                device="cpu",
                log=logger,
                want_spectrum=needs_spectrum(config),
                workspace=None,
                rng=RNGTree(config.scenario.seed).for_scenario(),
            )
            if pool is not None:
                safe_labels = {
                    label
                    for label, algo in algorithms.items()
                    if algo.capabilities.parallel
                    and not algo.capabilities.uses_gpu
                    and "<locals>" not in type(algo).__qualname__
                    and type(algo).__module__ != "__main__"
                }
                worker_config = point_config.model_copy(deep=True)
                worker_config.algorithms = [
                    item for item in worker_config.algorithms if item.get_label() in safe_labels
                ]
                local_algorithms = {
                    label: algo for label, algo in algorithms.items() if label not in safe_labels
                }
                if safe_labels:
                    from .parallel import execute_chunk

                    blocks = iter(
                        [
                            list(
                                range(start, min(config.trials, start + config.options.chunk_size))
                            )
                            for start in range(0, config.trials, config.options.chunk_size)
                        ]
                    )
                    pending = {}
                    trials = []
                    consecutive = {label: 0 for label in algorithms}
                    disabled: set[str] = set()

                    def submit_next() -> None:
                        indices = next(blocks, None)
                        if indices is not None:
                            future = pool.submit(
                                execute_chunk,
                                worker_config.model_dump(mode="json"),
                                point_idx,
                                indices,
                                {
                                    k: v
                                    for k, v in (algorithm_classes or {}).items()
                                    if k in safe_labels
                                },
                            )
                            pending[future] = indices

                    for _ in range(config.options.workers):
                        submit_next()
                    while pending:
                        if cancel_callback and cancel_callback():
                            cancelled = True
                        # 按试验序号消费结果，使连续错误策略不依赖工作进程完成顺序。
                        first_pending = min(pending, key=lambda future: pending[future][0])
                        completed, _ = wait(
                            [first_pending], timeout=0.1, return_when=FIRST_COMPLETED
                        )
                        for future in completed:
                            indices = pending.pop(future)
                            try:
                                block_results = future.result()
                            except Exception as exc:
                                raise RuntimeError(
                                    f"工作进程执行失败，请检查插件是否可以通过 spawn 导入：{exc}"
                                ) from exc
                            from .batch import execute_batches

                            local_batch = execute_batches(
                                point_config, point_idx, indices, local_algorithms, ctx
                            )
                            for trial in block_results:
                                random_index = (
                                    trial.trial_idx
                                    if config.options.common_random_numbers
                                    else point_idx * config.trials + trial.trial_idx
                                )
                                if local_algorithms:
                                    local_scene, _ = build_scene(point_config, random_index)
                                    local = run_trial(
                                        trial.trial_idx,
                                        local_scene,
                                        local_algorithms,
                                        rng_tree.for_trial(random_index),
                                        ctx,
                                        config.options.source_count,
                                        config.type == "single"
                                        and config.options.save_observations == "auto",
                                        local_batch.get(trial.trial_idx),
                                        save_spectrum(config),
                                    )
                                    trial.estimates.update(local.estimates)
                                    trial.errors.update(local.errors)
                                    trial.times_ms.update(local.times_ms)
                                    trial.error_details.update(local.error_details)
                                trial.errors.update(setup_errors)
                                for label in algorithms:
                                    if label in disabled:
                                        trial.estimates.pop(label, None)
                                        trial.times_ms.pop(label, None)
                                        trial.errors[label] = (
                                            "连续错误达到上限，本扫描点剩余试验已跳过"
                                        )
                                    else:
                                        consecutive[label] = (
                                            consecutive[label] + 1 if label in trial.errors else 0
                                        )
                                        if (
                                            consecutive[label]
                                            >= config.options.max_consecutive_errors
                                        ):
                                            disabled.add(label)
                                            local_algorithms.pop(label, None)
                                for item in worker_config.algorithms:
                                    if item.get_label() in disabled:
                                        item.enabled = False
                            trials.extend(block_results)
                            trials.sort(key=lambda trial: trial.trial_idx)
                            if checkpoint_callback:
                                checkpoint_callback(
                                    ExperimentResult(
                                        config.model_dump(),
                                        [
                                            *points,
                                            SweepPointResult(point_idx, sweep_val, list(trials)),
                                        ],
                                        {
                                            "status": "running",
                                            "generator_version": GENERATOR_VERSION,
                                            "start_time": start_time,
                                        },
                                    )
                                )
                            if progress_callback:
                                progress_callback(
                                    point_idx * config.trials + len(trials),
                                    total_trials,
                                    point_idx,
                                    total_points,
                                )
                            if not cancelled:
                                submit_next()
                    points.append(SweepPointResult(point_idx, sweep_val, trials))
                    if cancelled:
                        break
                    continue
            scenario_gen = scene
            # 运行所有试验
            trials = []

            consecutive = {label: 0 for label in algorithms}
            from .batch import execute_batches

            batch_cache = {}
            for trial_idx in range(config.trials):
                if cancel_callback and cancel_callback():
                    cancelled = True
                    break
                if trial_idx % config.options.chunk_size == 0:
                    indices = list(
                        range(trial_idx, min(config.trials, trial_idx + config.options.chunk_size))
                    )
                    batch_cache = execute_batches(point_config, point_idx, indices, algorithms, ctx)
                # 获取试验随机数管理器
                trial_rng = rng_tree.for_trial(
                    trial_idx
                    if config.options.common_random_numbers
                    else point_idx * config.trials + trial_idx
                )
                if point_config.scenario.sources.angles.mode == "random" or (
                    point_config.scenario.sources.correlation.mode == "coherent"
                    and point_config.scenario.sources.correlation.phases_deg == "random"
                ):
                    scenario_gen, _ = build_scene(
                        point_config,
                        trial_idx
                        if config.options.common_random_numbers
                        else point_idx * config.trials + trial_idx,
                    )

                # 运行试验
                result = run_trial(
                    trial_idx,
                    scenario_gen,
                    algorithms,
                    trial_rng,
                    ctx,
                    config.options.source_count,
                    config.type == "single" and config.options.save_observations == "auto",
                    batch_cache.get(trial_idx),
                    save_spectrum(config),
                )
                result.errors.update(setup_errors)
                for label in list(algorithms):
                    consecutive[label] = consecutive[label] + 1 if label in result.errors else 0
                    if consecutive[label] >= config.options.max_consecutive_errors:
                        setup_errors[label] = "连续错误达到上限，本扫描点剩余试验已跳过"
                        algorithms.pop(label)
                trials.append(result)
                if checkpoint_callback and (trial_idx + 1) % config.options.chunk_size == 0:
                    partial = ExperimentResult(
                        config.model_dump(),
                        [*points, SweepPointResult(point_idx, sweep_val, list(trials))],
                        {
                            "status": "running",
                            "generator_version": GENERATOR_VERSION,
                            "start_time": start_time,
                        },
                    )
                    checkpoint_callback(partial)
                if progress_callback is not None:
                    progress_callback(
                        point_idx * config.trials + trial_idx + 1,
                        total_trials,
                        point_idx,
                        total_points,
                    )

            points.append(
                SweepPointResult(
                    point_idx=point_idx,
                    sweep_value=sweep_val,
                    trials=trials,
                )
            )

            if checkpoint_callback and len(trials) % config.options.chunk_size:
                checkpoint_callback(
                    ExperimentResult(
                        config.model_dump(),
                        list(points),
                        {
                            "status": "running",
                            "generator_version": GENERATOR_VERSION,
                            "start_time": start_time,
                        },
                    )
                )
            if cancelled:
                break
    finally:
        if pool is not None:
            pool.shutdown(wait=True, cancel_futures=True)
        for algo in instances.values():
            try:
                algo.close()
            except Exception:
                logger.exception("关闭算法资源失败")

    # 元信息
    metadata = {
        "status": "cancelled" if cancelled else "completed",
        "warnings": [issue for issue in validation_issues if issue["level"] == "warning"],
        "workers": config.options.workers,
        "timing_note": "并行运行，计时仅供参考" if config.options.workers > 1 else "串行逐次计时",
        "start_time": start_time,
        "elapsed_seconds": time.time() - start_time,
        "num_points": len(sweep_values),
        "generator_version": GENERATOR_VERSION,
        "num_trials": config.trials,
    }
    from ..storage.provenance import capture

    metadata.update(capture(config, instances))

    return ExperimentResult(
        config=config.model_dump(),
        points=points,
        metadata=metadata,
    )


GENERATOR_VERSION = 3


def expand_point(config: ExperimentConfig, value: float | None) -> ExperimentConfig:
    """按数据格式 3.8 节展开数值扫描路径，并重新校验配置。"""
    import re

    data = config.model_dump(mode="json")
    if value is not None and config.sweep:
        tokens = re.findall(r"[^.\[\]]+", config.sweep.path)
        node = data
        for token in tokens[:-1]:
            if isinstance(node, list):
                node = (
                    node[int(token)]
                    if token.isdigit()
                    else next(x for x in node if (x.get("label") or x.get("type")) == token)
                )
            else:
                node = node[token]
        key = int(tokens[-1]) if isinstance(node, list) else tokens[-1]
        if isinstance(node[key], bool) or (
            node[key] is not None and not isinstance(node[key], int | float)
        ):
            raise ValueError("扫描路径必须指向数值字段，请选择数值字段旁的扫描按钮")
        node[key] = (
            int(value) if isinstance(node[key], int) and float(value).is_integer() else value
        )
    result = ExperimentConfig.model_validate(data)
    result._workspace = config._workspace
    return result


def build_scene(
    config: ExperimentConfig, trial_idx: int = 0
) -> tuple[ScenarioGenerator, ArrayDescriptor]:
    """使用配置中的真实参数创建场景和误差实例。"""
    from ..plugins import resolve_plugin

    sc = config.scenario
    array_class = resolve_plugin("array", sc.array.type, sc.array.origin)
    params = array_class.Params(**sc.array.params)
    array = ArrayDescriptor(
        type=sc.array.type,
        params=params.model_dump(),
        positions=array_class().positions(params),
        model=array_class(),
    )
    if isinstance(sc.sources.K, int):
        k = sc.sources.K
    else:
        if sc.sources.angles.mode != "random":
            raise ValueError("随机信源数要求随机角度模式")
        rng = np.random.default_rng(np.random.SeedSequence(sc.seed, spawn_key=(8, trial_idx)))
        if any(not 1 <= n < array.M for n in sc.sources.K.values):
            raise ValueError("所有随机信源数取值都必须大于零且小于阵元数")
        weights = sc.sources.K.weights
        probabilities = None if weights is None else np.asarray(weights) / np.sum(weights)
        k = int(rng.choice(sc.sources.K.values, p=probabilities))
    if not 1 <= k < array.M:
        raise ValueError("信源数必须小于阵元数")
    angle_config = sc.sources.angles
    if angle_config.mode == "fixed":
        angles = np.asarray(
            angle_config.values if angle_config.values is not None else np.linspace(-10, 10, k),
            dtype=float,
        )
    elif angle_config.mode == "separation":
        if k != 2 or angle_config.delta is None or angle_config.delta <= 0:
            raise ValueError("角度间隔模式要求两个信源且间隔大于零")
        angles = angle_config.center + np.asarray([-angle_config.delta / 2, angle_config.delta / 2])
    else:
        bounds = angle_config.range_deg
        if not bounds or bounds[0] >= bounds[1]:
            raise ValueError("随机角度要求有效的起止范围")
        rng = np.random.default_rng(np.random.SeedSequence(sc.seed, spawn_key=(9, trial_idx)))
        gap = angle_config.min_separation
        width = bounds[1] - bounds[0] - gap * (k - 1)
        if width <= 0:
            raise ValueError("随机角度范围无法容纳所需信源数和最小间隔")
        for _ in range(10000):
            angles = np.sort(rng.uniform(bounds[0], bounds[1], size=k))
            if k == 1 or np.min(np.diff(angles)) >= gap:
                break
        else:
            raise ValueError("随机角度拒绝采样超过 10000 次，请扩大范围或减小最小间隔")
    if len(angles) != k or np.any(np.abs(angles) >= 90):
        raise ValueError("角度数量必须等于信源数且位于 (-90, 90) 度")
    snr = np.asarray(sc.sources.snr_db)
    if snr.ndim > 0 and len(snr) != k:
        raise ValueError("逐信源 SNR 数量必须等于信源数")
    powers = np.broadcast_to(sc.noise_power * 10 ** (snr / 10), (k,)).copy()
    corr_config = sc.sources.correlation
    if corr_config.mode == "partial":
        corr = CorrelationMatrix.partial_correlated(
            powers, corr_config.rho_mag or 0, corr_config.rho_phase_deg
        )
    elif corr_config.mode == "coherent":
        phases = corr_config.phases_deg
        if phases == "random":
            rng = np.random.default_rng(np.random.SeedSequence(sc.seed, spawn_key=(10, trial_idx)))
            phases = rng.uniform(-180, 180, k - 1).tolist()
        if len(phases) != k - 1:
            raise ValueError("相干相位列表长度必须为 K−1")
        corr = CorrelationMatrix.coherent(powers, np.exp(1j * np.deg2rad([0, *phases])))
    else:
        corr = CorrelationMatrix.independent(powers)
    impairments = []
    for index, imp in enumerate(sc.impairments):
        if not imp.enabled:
            continue
        plugin = resolve_plugin("impairment", imp.type, imp.origin)()
        rng = np.random.default_rng(np.random.SeedSequence(sc.seed, spawn_key=(11, index)))
        impairments.append(
            ImpairmentInstance(
                plugin,
                plugin.Params(**imp.params),
                imp.realization,
                dict(plugin.sample(rng, array.M)) if imp.realization == "fixed" else None,
            )
        )
    scene = ScenarioConfig(array, k, angles, sc.sources.snr_db, sc.snapshots, corr, sc.noise_power)
    return ScenarioGenerator(scene, impairments), array


def _create_ula_positions(M: int, d: float) -> np.ndarray:
    """创建 ULA 阵元位置。"""
    return np.column_stack(
        [
            np.arange(M) * d,
            np.zeros(M),
            np.zeros(M),
        ]
    )


def _load_algorithms(
    config: ExperimentConfig,
    array: ArrayDescriptor,
    instances: dict[str, Algorithm] | None = None,
    setup_errors: dict[str, str] | None = None,
    algorithm_classes: dict[str, type[Algorithm]] | None = None,
) -> dict[str, Algorithm]:
    """加载算法。

    Args:
        config: 实验配置
        array: 阵列描述
        instances: 已加载实例，用于跨扫描点复用并统一释放
        setup_errors: 接收各算法初始化错误；未提供时直接抛出
        algorithm_classes: 脚本模式直接传入的类

    Returns:
        算法字典 {label: algorithm}
    """
    from ..plugins import resolve_algorithm

    algorithms = {}
    ctx = RunContext(
        device="cpu",
        log=logger,
        want_spectrum=False,
        workspace=None,
        rng=RNGTree(config.scenario.seed).for_scenario(),
    )

    for algo_config in config.algorithms:
        if not algo_config.enabled:
            continue

        label = algo_config.get_label()
        algo_id = algo_config.id

        try:
            AlgoClass = (algorithm_classes or {}).get(label)
            if AlgoClass is None:
                AlgoClass = resolve_algorithm(algo_id, algo_config.origin)
            from ..models import parameters

            params = parameters(AlgoClass, algo_config.params, config._workspace)
            source_count = config.scenario.sources.K
            counts = [source_count] if isinstance(source_count, int) else source_count.values
            for count in counts:
                issues = AlgoClass.check(params, array, count) or []
                errors = [issue.message for issue in issues if issue.level == "error"]
                if errors:
                    raise ValueError("；".join(errors))
            algo_config.params = AlgoClass.Params(**algo_config.params).model_dump(mode="json")
            algo = instances.get(label) if instances else None
            if algo is None:
                algo = AlgoClass()
                if instances is not None:
                    instances[label] = algo
                algo.load(params, ctx)
            previous = getattr(algo, "_loaded_parameters", None)
            current = params.model_dump(mode="json")
            if previous is not None and any(
                field.get("x-reload") and previous.get(name) != current.get(name)
                for name, field in AlgoClass.Params.model_json_schema()
                .get("properties", {})
                .items()
            ):
                algo.close()
                algo.load(params, ctx)
            algo._loaded_parameters = current
            algo.configure(params, array, ctx)
            algo._current_mask = array.element_mask
            algorithms[label] = algo
        except Exception as exc:
            if setup_errors is None:
                raise
            setup_errors[label] = f"load/configure 失败：{exc}"
            logger.exception("算法初始化失败：%s", label)

    return algorithms


def _warmup_algorithms(
    scenario_gen: ScenarioGenerator,
    algorithms: dict[str, Algorithm],
    rng_tree: RNGTree,
) -> None:
    """预热算法。

    使用第一次试验数据预热，结果丢弃。
    """
    ctx = RunContext(
        device="cpu",
        log=logger,
        want_spectrum=False,
        workspace=None,
        rng=rng_tree.for_scenario(),
    )

    # 生成预热数据
    trial_rng = rng_tree.for_trial(0)
    obs = scenario_gen.generate(trial_rng)

    # 预热所有算法
    for label, algo in algorithms.items():
        try:
            _ = algo.estimate(obs, ctx)
        except Exception as e:
            logger.warning(f"算法 {label} 预热失败: {e}")
