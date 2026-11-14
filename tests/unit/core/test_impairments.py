"""测试误差插件。"""

import numpy as np
import pytest
from arena_api import ComplexValue

from arena.core.impairments import ElementFailure, GainPhase, MutualCoupling, PositionError


@pytest.fixture
def rng():
    """固定随机数生成器。"""
    return np.random.Generator(np.random.PCG64(42))


def test_position_error(rng):
    """测试位置误差。"""
    M = 8

    # 标称位置（ULA）
    positions = np.column_stack([
        np.arange(M) * 0.5,
        np.zeros(M),
        np.zeros(M),
    ])

    # 创建插件
    imp = PositionError()
    params = PositionError.Params(sigma=0.01, axes="x")

    # 抽取随机量
    draw = imp.sample(rng, M)

    assert "z" in draw
    assert draw["z"].shape == (M, 3)

    # 参考阵元误差为 0
    assert np.allclose(draw["z"][0, :], 0.0)

    # 应用误差
    actual_positions = imp.apply(positions, draw, params)

    assert actual_positions.shape == (M, 3)

    # 参考阵元位置不变
    assert np.allclose(actual_positions[0, :], positions[0, :])

    # 其他阵元有偏移
    offsets = actual_positions - positions
    assert np.any(np.abs(offsets[1:, 0]) > 0)  # x 轴有偏移
    assert np.allclose(offsets[:, 1], 0.0)      # y 轴无偏移
    assert np.allclose(offsets[:, 2], 0.0)      # z 轴无偏移

    # 描述
    desc = imp.describe(draw, params, M)
    assert "offset" in desc
    assert desc["offset"].shape == (M, 3)


def test_gain_phase(rng):
    """测试幅相误差。"""
    M, K = 8, 2

    # 真实流形
    angles = np.array([-10.0, 10.0])
    A = np.random.randn(M, K) + 1j * np.random.randn(M, K)

    # 创建插件
    imp = GainPhase()
    params = GainPhase.Params(sigma_g=0.05, sigma_phi_deg=5.0)

    # 抽取随机量
    draw = imp.sample(rng, M)

    assert "z_g" in draw and "z_phi" in draw
    assert draw["z_g"].shape == (M,)
    assert draw["z_phi"].shape == (M,)

    # 参考阵元误差为 0
    assert np.allclose(draw["z_g"][0], 0.0)
    assert np.allclose(draw["z_phi"][0], 0.0)

    # 应用误差
    A_modified = imp.apply(A, draw, params)

    assert A_modified.shape == (M, K)

    # 参考阵元不变
    assert np.allclose(A_modified[0, :], A[0, :])

    # 其他阵元有变化
    assert not np.allclose(A_modified[1:, :], A[1:, :])

    # 描述
    desc = imp.describe(draw, params, M)
    assert "gain" in desc and "phase_deg" in desc
    assert desc["gain"].shape == (M,)
    assert desc["phase_deg"].shape == (M,)

    # 参考阵元增益为 1，相位为 0
    assert np.isclose(desc["gain"][0], 1.0)
    assert np.isclose(desc["phase_deg"][0], 0.0)


def test_gain_phase_fixed(rng):
    """测试固定幅相误差。"""
    M, K = 8, 2

    A = np.random.randn(M, K) + 1j * np.random.randn(M, K)

    # 固定增益和相位
    fixed_gains = [1.0, 0.9, 1.1, 1.05, 0.95, 1.0, 1.0, 1.0]
    fixed_phases = [0.0, 5.0, -5.0, 10.0, -10.0, 0.0, 0.0, 0.0]

    imp = GainPhase()
    params = GainPhase.Params(
        fixed_gains=fixed_gains,
        fixed_phases_deg=fixed_phases,
    )

    draw = imp.sample(rng, M)

    A_modified = imp.apply(A, draw, params)

    # 描述
    desc = imp.describe(draw, params, M)

    # 检查使用了固定值
    assert np.allclose(desc["gain"], fixed_gains)
    assert np.allclose(desc["phase_deg"], fixed_phases)


def test_mutual_coupling(rng):
    """测试互耦误差。"""
    M, K = 8, 2

    A = np.random.randn(M, K) + 1j * np.random.randn(M, K)

    # 创建插件
    imp = MutualCoupling()
    params = MutualCoupling.Params(
        coefficients=[
            ComplexValue(magnitude=0.3, phase_deg=30),
            ComplexValue(magnitude=0.1, phase_deg=-20),
        ],
        scale=1.0,
    )

    # 抽取随机量（空）
    draw = imp.sample(rng, M)
    assert len(draw) == 0

    # 应用误差
    A_coupled = imp.apply(A, draw, params)

    assert A_coupled.shape == (M, K)

    # 应该不等于原流形
    assert not np.allclose(A_coupled, A)

    # 描述
    desc = imp.describe(draw, params, M)
    assert "coupling_matrix" in desc
    C = desc["coupling_matrix"]

    assert C.shape == (M, M)

    # 主对角线为 1
    assert np.allclose(np.diag(C), 1.0)

    # 对称
    assert np.allclose(C, C.T)


def test_element_failure_zero(rng):
    """测试阵元故障（置零模式）。"""
    M, N = 8, 100

    X = np.random.randn(M, N) + 1j * np.random.randn(M, N)

    # 创建插件
    imp = ElementFailure()
    params = ElementFailure.Params(
        indices=None,  # 随机选择
        count=2,
        mode="zero",
        known=True,
    )

    # 抽取随机量
    draw = imp.sample(rng, M)

    assert "permutation" in draw
    assert len(draw["permutation"]) == M - 1  # 排除第 0 个

    # 确定故障阵元
    desc = imp.describe(draw, params, M)
    failure_indices = desc["failure_indices"]

    assert len(failure_indices) == 2
    assert 0 not in failure_indices  # 第 0 个不会故障

    # 应用故障
    X_failed = imp.apply(X, draw, params)

    # 故障阵元输出为 0
    assert np.allclose(X_failed[failure_indices, :], 0.0)

    # 其他阵元不变
    normal_indices = np.setdiff1d(np.arange(M), failure_indices)
    assert np.allclose(X_failed[normal_indices, :], X[normal_indices, :])

    # 算法已知
    mask = imp.known_mask(draw, params, M)
    assert mask is not None
    assert mask.shape == (M,)
    assert not mask[failure_indices].any()  # 故障阵元为 False
    assert mask[normal_indices].all()       # 正常阵元为 True


def test_element_failure_noise_only(rng):
    """测试阵元故障（仅噪声模式）。"""
    M, N = 8, 100

    # 无噪数据（A·S）
    AS = np.random.randn(M, N) + 1j * np.random.randn(M, N)

    # 创建插件
    imp = ElementFailure()
    params = ElementFailure.Params(
        count=1,
        mode="noise_only",
        known=False,
    )

    # 阶段
    stage = ElementFailure.stage_for(params)
    assert stage == "signal"

    # 抽取随机量
    draw = imp.sample(rng, M)

    # 应用故障
    AS_failed = imp.apply(AS, draw, params)

    # 故障阵元信号置零（后续会加噪声）
    desc = imp.describe(draw, params, M)
    failure_indices = desc["failure_indices"]

    assert np.allclose(AS_failed[failure_indices, :], 0.0)

    # 算法不知道
    mask = imp.known_mask(draw, params, M)
    assert mask is None


def test_element_failure_fixed_indices(rng):
    """测试指定故障阵元。"""
    M, N = 8, 100

    X = np.random.randn(M, N) + 1j * np.random.randn(M, N)

    # 固定故障阵元
    imp = ElementFailure()
    params = ElementFailure.Params(
        indices=[2, 5],
        mode="zero",
    )

    draw = imp.sample(rng, M)

    X_failed = imp.apply(X, draw, params)

    # 指定的阵元故障
    assert np.allclose(X_failed[2, :], 0.0)
    assert np.allclose(X_failed[5, :], 0.0)

    # 其他阵元不变
    for i in [0, 1, 3, 4, 6, 7]:
        assert np.allclose(X_failed[i, :], X[i, :])


def test_element_failure_stage_switching():
    """测试阶段根据模式切换。"""
    # zero 模式 → output 阶段
    params_zero = ElementFailure.Params(mode="zero")
    assert ElementFailure.stage_for(params_zero) == "output"

    # noise_only 模式 → signal 阶段
    params_noise = ElementFailure.Params(mode="noise_only")
    assert ElementFailure.stage_for(params_noise) == "signal"
