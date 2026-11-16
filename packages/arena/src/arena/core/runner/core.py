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

    # 构建场景配置（简化版）
    from arena_api import ArrayDescriptor

    # 阵列
    array = ArrayDescriptor(
        type=config.scenario.array.type,
        params=config.scenario.array.params,
        positions=_create_ula_positions(
            config.scenario.array.params["M"],
            config.scenario.array.params["d"],
        ),
    )

    # 信源角度（简化：固定角度）
    if config.scenario.sources.angles.mode == "fixed":
        angles = np.array(config.scenario.sources.angles.values or [-10.0, 10.0])
    else:
        # 简化：随机角度
        angles = np.array([-10.0, 10.0])

    # 信源功率
    K = config.scenario.sources.K
    snr_db = config.scenario.sources.snr_db
    noise_power = config.scenario.noise_power
    signal_power = noise_power * (10 ** (snr_db / 10))
    powers = np.full(K, signal_power)

    # 相关性
    corr_mode = config.scenario.sources.correlation.mode
    if corr_mode == "none":
        corr = CorrelationMatrix.independent(powers)
    elif corr_mode == "coherent":
        alpha = np.ones(K, dtype=complex)
        corr = CorrelationMatrix.coherent(powers, alpha)
    else:
        corr = CorrelationMatrix.independent(powers)

    # 场景配置
    scenario_config = ScenarioConfig(
        array=array,
        K=K,
        angles=angles,
        snr_db=snr_db,
        N=config.scenario.snapshots,
        correlation=corr,
        noise_power=noise_power,
    )

    # 误差实例（简化：暂不支持）
    impairments: list[ImpairmentInstance] = []

    # 创建场景生成器
    scenario_gen = ScenarioGenerator(scenario_config, impairments)

    # 加载算法
    algorithms = _load_algorithms(config, array)

    # 预热
    if config.options.warmup:
        logger.info("预热算法...")
        _warmup_algorithms(scenario_gen, algorithms, rng_tree)

    # 运行上下文
    ctx = RunContext(
        device="cpu",
        log=logger,
        want_spectrum=False,
        workspace=None,
        rng=np.random.Generator(np.random.PCG64(42)),
    )

    # 确定扫描点
    if config.type == "sweep" and config.sweep:
        sweep_values = config.sweep.values
    else:
        sweep_values = [None]  # 单点

    # 运行所有扫描点
    points = []

    total_points = len(sweep_values)
    total_trials = total_points * config.trials

    for point_idx, sweep_val in enumerate(sweep_values):
        logger.info(f"运行扫描点 {point_idx + 1}/{len(sweep_values)}")

        # 运行所有试验
        trials = []

        for trial_idx in range(config.trials):
            # 获取试验随机数管理器
            trial_rng = rng_tree.for_trial(trial_idx)

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
        "num_trials": config.trials,
    }

    return ExperimentResult(
        config=config.model_dump(),
        points=points,
        metadata=metadata,
    )


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
        rng=np.random.Generator(np.random.PCG64(42)),
    )

    for algo_config in config.algorithms:
        if not algo_config.enabled:
            continue

        label = algo_config.get_label()
        algo_id = algo_config.id

        if algo_id not in builtin_algorithms:
            logger.warning(f"未知算法: {algo_id}，跳过")
            continue

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
        rng=np.random.Generator(np.random.PCG64(42)),
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
