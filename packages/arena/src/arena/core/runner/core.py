"""Runner 核心实现。"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable

import numpy as np

from arena_api import Algorithm, ArrayDescriptor, RunContext

from ..config import ExperimentConfig
from ..rng import RNGTree, TrialRNG
from ..scenario import ImpairmentInstance, ScenarioConfig, ScenarioGenerator
from ..signals import CorrelationMatrix
from .results import ExperimentResult, SweepPointResult, TrialResult

logger = logging.getLogger(__name__)


def run_trial(
    trial_idx: int,
    scenario_gen: ScenarioGenerator,
    algorithms: dict[str, Algorithm],
    trial_rng: TrialRNG,
    ctx: RunContext,
) -> TrialResult:
    """运行单次试验。

    Args:
        trial_idx: 试验索引
        scenario_gen: 场景生成器
        algorithms: 算法字典 {label: algorithm}
        trial_rng: 试验随机数管理器
        ctx: 运行上下文

    Returns:
        试验结果
    """
    # 生成观测数据
    obs = scenario_gen.generate(trial_rng)

    # 运行所有算法
    estimates = {}
    errors = {}
    times_ms = {}

    for label, algo in algorithms.items():
        try:
            # 计时
            start = time.perf_counter()
            est = algo.estimate(obs, ctx)
            elapsed = (time.perf_counter() - start) * 1000  # 毫秒

            estimates[label] = est
            times_ms[label] = elapsed

        except Exception as e:
            logger.error(f"算法 {label} 在试验 {trial_idx} 出错: {e}")
            errors[label] = str(e)

    return TrialResult(
        trial_idx=trial_idx,
        estimates=estimates,
        errors=errors,
        times_ms=times_ms,
        truth_angles=scenario_gen.config.angles.copy(),
    )


def run_experiment(
    config: ExperimentConfig,
    progress_callback: Callable[[int, int, int, int], None] | None = None,
) -> ExperimentResult:
    """运行实验。

    Args:
        config: 实验配置
        progress_callback: 可选进度回调，参数为已完成试验数、总试验数、当前扫描点和扫描点总数

    Returns:
        实验结果
    """
    start_time = time.time()

    # 验证配置
    config.validate_experiment()

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
    points = []

    total_points = len(sweep_values)
    total_trials = total_points * config.trials

    for point_idx, sweep_val in enumerate(sweep_values):
        logger.info(f"运行扫描点 {point_idx + 1}/{len(sweep_values)}")

        point_config = expand_point(config, sweep_val)
        scene, array = build_scene(point_config)
        algorithms = _load_algorithms(point_config, array)
        if config.options.warmup:
            _warmup_algorithms(scene, algorithms, RNGTree(config.scenario.seed))
        ctx = RunContext(
            device="cpu",
            log=logger,
            want_spectrum=config.type == "single",
            workspace=None,
            rng=RNGTree(config.scenario.seed).for_scenario(),
        )
        scenario_gen = scene
        # 运行所有试验
        trials = []

        for trial_idx in range(config.trials):
            # 获取试验随机数管理器
            trial_rng = rng_tree.for_trial(
                trial_idx
                if config.options.common_random_numbers
                else point_idx * config.trials + trial_idx
            )
            if point_config.scenario.sources.angles.mode == "random":
                scenario_gen, _ = build_scene(point_config, trial_idx)

            # 运行试验
            result = run_trial(
                trial_idx,
                scenario_gen,
                algorithms,
                trial_rng,
                ctx,
            )
            trials.append(result)
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

    # 元信息
    metadata = {
        "start_time": start_time,
        "elapsed_seconds": time.time() - start_time,
        "num_points": len(sweep_values),
        "generator_version": GENERATOR_VERSION,
        "num_trials": config.trials,
    }

    return ExperimentResult(
        config=config.model_dump(),
        points=points,
        metadata=metadata,
    )


GENERATOR_VERSION = 2


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
                    else next(x for x in node if x.get("label", x.get("type")) == token)
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
    return result


def build_scene(
    config: ExperimentConfig, trial_idx: int = 0
) -> tuple[ScenarioGenerator, ArrayDescriptor]:
    """使用配置中的真实参数创建场景和误差实例。"""
    from ..arrays import ULA
    from ..impairments import ElementFailure, GainPhase, MutualCoupling, PositionError

    sc = config.scenario
    if sc.array.type != ULA.id:
        raise ValueError("未知阵列类型，请从 Schema 中选择可用阵列")
    params = ULA.Params(**sc.array.params)
    array = ArrayDescriptor(
        type=sc.array.type, params=params.model_dump(), positions=ULA().positions(params)
    )
    if isinstance(sc.sources.K, int):
        k = sc.sources.K
    else:
        if sc.sources.angles.mode != "random":
            raise ValueError("随机信源数要求随机角度模式")
        rng = np.random.default_rng(np.random.SeedSequence(sc.seed, spawn_key=(8, trial_idx)))
        if any(not 1 <= n < array.M for n in sc.sources.K.values):
            raise ValueError("所有随机信源数取值都必须大于零且小于阵元数")
        k = int(rng.choice(sc.sources.K.values))
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
        angles = np.sort(rng.uniform(bounds[0], bounds[0] + width, size=k)) + np.arange(k) * gap
    if len(angles) != k or np.any(np.abs(angles) >= 90):
        raise ValueError("角度数量必须等于信源数且位于 (-90, 90) 度")
    snr = np.asarray(sc.sources.snr_db)
    if snr.ndim > 0 and len(snr) != k:
        raise ValueError("逐信源 SNR 数量必须等于信源数")
    powers = np.broadcast_to(sc.noise_power * 10 ** (snr / 10), (k,)).copy()
    corr_config = sc.sources.correlation
    if corr_config.mode == "partial":
        corr = CorrelationMatrix.partial_correlated(powers, corr_config.rho_mag or 0)
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
    registry = {cls.id: cls for cls in (GainPhase, PositionError, MutualCoupling, ElementFailure)}
    impairments = []
    for index, imp in enumerate(sc.impairments):
        if not imp.enabled:
            continue
        if imp.type not in registry:
            raise ValueError("未知误差插件，请刷新配置 Schema")
        plugin = registry[imp.type]()
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
) -> dict[str, Algorithm]:
    """加载算法。

    Args:
        config: 实验配置
        array: 阵列描述

    Returns:
        算法字典 {label: algorithm}
    """
    from ..algorithms import CBF, ESPRIT, MUSIC, MVDR, RootMUSIC

    # 内置算法映射
    builtin_algorithms = {
        "cbf": CBF,
        "mvdr": MVDR,
        "music": MUSIC,
        "root_music": RootMUSIC,
        "esprit": ESPRIT,
    }

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

        if algo_id not in builtin_algorithms:
            raise ValueError(f"未知算法: {algo_id}，请选择已注册算法")

        # 创建算法实例
        AlgoClass = builtin_algorithms[algo_id]
        algo = AlgoClass()

        # 配置算法
        params_dict = algo_config.params
        params = AlgoClass.Params(**params_dict)
        algo.configure(params, array, ctx)

        algorithms[label] = algo

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
