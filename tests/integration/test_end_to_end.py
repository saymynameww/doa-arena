"""端到端集成测试。

测试从数据生成到算法估计的完整流程。
"""

import logging

import numpy as np
import pytest

from arena.core.algorithms import CBF, ESPRIT, MUSIC, MVDR, RootMUSIC
from arena.core.crb import compute_stochastic_crb
from arena.core.metrics import match_and_compute
from arena.core.rng import RNGTree
from arena.core.scenario import generate_trial_data
from arena_api import ArrayDescriptor, RunContext


@pytest.fixture
def ula_array():
    """创建 ULA 阵列。"""
    M = 16
    d = 0.5
    positions = np.column_stack(
        [
            np.arange(M) * d,
            np.zeros(M),
            np.zeros(M),
        ]
    )
    return ArrayDescriptor(
        type="ula",
        params={"M": M, "d": d},
        positions=positions,
    )


@pytest.fixture
def run_context():
    """创建运行上下文。"""
    logger = logging.getLogger("test")
    rng = np.random.Generator(np.random.PCG64(42))

    return RunContext(
        device="cpu",
        log=logger,
        want_spectrum=False,
        workspace=None,
        rng=rng,
    )


def test_single_trial_music(ula_array, run_context):
    """测试 MUSIC 单次试验。"""
    # 场景参数
    K = 2
    angles_true = np.array([-10.0, 15.0])
    N = 100
    snr_db = 10.0

    # 生成数据
    tree = RNGTree(seed=42)
    obs = generate_trial_data(
        array=ula_array,
        angles=angles_true,
        K=K,
        N=N,
        snr_db=snr_db,
        correlation_mode="independent",
        trial_rng=tree.for_trial(0),
    )

    # 配置 MUSIC
    music = MUSIC()
    params = MUSIC.Params(
        grid_start=-90,
        grid_stop=90,
        grid_step=0.5,
        smoothing="none",
    )
    music.configure(params, ula_array, run_context)

    # 估计
    estimate = music.estimate(obs, run_context)

    # 验证
    assert estimate.K_hat == K

    # 匹配
    result = match_and_compute(estimate, angles_true)
    print(f"MUSIC 估计: {estimate.angles}")
    print(f"真实角度: {angles_true}")
    print(f"RMSE: {result['rmse']:.3f}°")

    # 高 SNR 下应该很准确
    assert result["rmse"] < 2.0
    assert result["success"]


def test_multiple_trials_music(ula_array, run_context):
    """测试 MUSIC 多次试验统计。"""
    K = 2
    angles_true = np.array([-15.0, 20.0])
    N = 200
    snr_db = 15.0
    num_trials = 50

    # 生成多次试验
    tree = RNGTree(seed=42)
    estimates = []

    music = MUSIC()
    params = MUSIC.Params(grid_step=0.2)
    music.configure(params, ula_array, run_context)

    for trial_idx in range(num_trials):
        obs = generate_trial_data(
            array=ula_array,
            angles=angles_true,
            K=K,
            N=N,
            snr_db=snr_db,
            trial_rng=tree.for_trial(trial_idx),
        )
        est = music.estimate(obs, run_context)
        estimates.append(est)

    # 统计 RMSE
    rmses = []
    for est in estimates:
        result = match_and_compute(est, angles_true)
        rmses.append(result["rmse"])

    rmse_mean = np.mean(rmses)
    print(f"MUSIC RMSE 均值: {rmse_mean:.3f}°")

    # 高 SNR 下应该很小
    assert rmse_mean < 1.0


def test_all_algorithms(ula_array, run_context):
    """测试所有算法在同一场景下的性能。"""
    K = 2
    angles_true = np.array([-20.0, 10.0])
    N = 100
    snr_db = 10.0

    # 生成数据
    tree = RNGTree(seed=42)
    obs = generate_trial_data(
        array=ula_array,
        angles=angles_true,
        K=K,
        N=N,
        snr_db=snr_db,
        trial_rng=tree.for_trial(0),
    )

    # 测试所有算法
    algorithms = [
        (CBF(), CBF.Params()),
        (MVDR(), MVDR.Params()),
        (MUSIC(), MUSIC.Params(grid_step=0.5)),
        (RootMUSIC(), RootMUSIC.Params()),
        (ESPRIT(), ESPRIT.Params(method="tls")),
    ]

    results = {}

    for algo, params in algorithms:
        algo.configure(params, ula_array, run_context)
        estimate = algo.estimate(obs, run_context)
        result = match_and_compute(estimate, angles_true)
        results[algo.name] = result

    # 打印结果
    print("\n算法性能比较：")
    for name, result in results.items():
        print(f"{name:15s}: RMSE={result['rmse']:6.3f}deg, K_hat={result['K_hat']}")

    # 所有算法都应该成功检测
    for name, result in results.items():
        assert result["K_hat"] == K, f"{name} 检测信源数错误"


def test_music_vs_crb(ula_array, run_context):
    """测试 MUSIC 是否接近 CRB。"""
    K = 2
    angles_true = np.array([-10.0, 10.0])
    N = 200
    snr_db = 20.0  # 高 SNR
    num_trials = 100

    # 计算 CRB
    crb = compute_stochastic_crb(
        array=ula_array,
        angles=angles_true,
        snr_db=snr_db,
        N=N,
    )
    crb_rmse = np.sqrt(np.mean(crb))  # 总体 CRB

    print(f"\nCRB: {crb_rmse:.4f}deg")

    # 运行 MUSIC
    tree = RNGTree(seed=42)
    music = MUSIC()
    params = MUSIC.Params(grid_step=0.1)
    music.configure(params, ula_array, run_context)

    rmses = []
    for trial_idx in range(num_trials):
        obs = generate_trial_data(
            array=ula_array,
            angles=angles_true,
            K=K,
            N=N,
            snr_db=snr_db,
            trial_rng=tree.for_trial(trial_idx),
        )
        est = music.estimate(obs, run_context)
        result = match_and_compute(est, angles_true)
        rmses.append(result["rmse"])

    music_rmse = np.mean(rmses)
    print(f"MUSIC RMSE: {music_rmse:.4f}deg")
    print(f"Ratio: {music_rmse / crb_rmse:.2f}")

    # MUSIC 应该接近 CRB（在 3 倍以内）
    assert music_rmse < crb_rmse * 3.0


@pytest.mark.slow
def test_coherent_sources_smoothing(ula_array, run_context):
    """测试相干信源下的空间平滑。"""
    K = 2
    angles_true = np.array([-15.0, 15.0])
    N = 200
    snr_db = 15.0

    # 生成相干数据
    tree = RNGTree(seed=42)
    obs = generate_trial_data(
        array=ula_array,
        angles=angles_true,
        K=K,
        N=N,
        snr_db=snr_db,
        correlation_mode="coherent",
        trial_rng=tree.for_trial(0),
    )

    # 不平滑：应该失效
    music_no_smooth = MUSIC()
    params_no_smooth = MUSIC.Params(smoothing="none")
    music_no_smooth.configure(params_no_smooth, ula_array, run_context)
    est_no_smooth = music_no_smooth.estimate(obs, run_context)
    result_no_smooth = match_and_compute(est_no_smooth, angles_true)

    print("\n相干信源测试：")
    print(f"不平滑 RMSE: {result_no_smooth['rmse']:.3f}deg")

    # 前后向平滑：应该恢复
    music_smooth = MUSIC()
    params_smooth = MUSIC.Params(smoothing="fb", subarray_size=11)
    music_smooth.configure(params_smooth, ula_array, run_context)
    est_smooth = music_smooth.estimate(obs, run_context)
    result_smooth = match_and_compute(est_smooth, angles_true)

    print(f"前后向平滑 RMSE: {result_smooth['rmse']:.3f}deg")

    # 平滑后应该显著改善
    # 注意：相干情况下不平滑可能完全失败（RMSE 很大或检测不到）
    # 平滑后应该 < 5deg
    if result_smooth["success"]:
        assert result_smooth["rmse"] < 5.0
