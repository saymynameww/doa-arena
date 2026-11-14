"""测试 arena_api 核心类型。"""

import numpy as np
import pytest
from arena_api import ArrayDescriptor, Estimate, Observation, Spectrum


def test_array_descriptor_ula():
    """测试 ULA 阵列描述。"""
    M = 8
    d = 0.5

    # ULA 位置
    positions = np.column_stack([
        np.arange(M) * d,
        np.zeros(M),
        np.zeros(M),
    ])

    array = ArrayDescriptor(
        type="ula",
        params={"M": M, "d": d},
        positions=positions,
    )

    assert array.M == M
    assert array.ula_spacing == d
    assert np.all(array.element_mask)

    # 测试导向矢量
    angles = np.array([-10, 0, 10])
    A = array.steering(angles)

    assert A.shape == (M, 3)
    assert A.dtype == np.complex128

    # 中心角度 (0°) 应该是全 1
    assert np.allclose(np.abs(A[:, 1]), 1.0)


def test_observation():
    """测试观测数据。"""
    M, N = 8, 100
    K = 2

    # 生成测试数据
    X = np.random.randn(M, N) + 1j * np.random.randn(M, N)

    obs = Observation(X=X, K=K)

    assert obs.M == M
    assert obs.N == N
    assert obs.K == K

    # 测试协方差
    R = obs.covariance()
    assert R.shape == (M, M)

    # 协方差应该是 Hermitian
    assert np.allclose(R, R.conj().T)


def test_estimate():
    """测试估计结果。"""
    angles = np.array([-10.5, 5.3])
    est = Estimate.from_angles(angles)

    assert est.K_hat == 2
    assert np.allclose(est.angles, angles)


def test_spectrum():
    """测试空间谱。"""
    grid = np.linspace(-90, 90, 181)
    values = np.random.rand(181)

    spec = Spectrum(grid=grid, values=values, kind="pseudo")

    assert spec.grid.shape == spec.values.shape
    assert len(spec.grid) == 181


def test_readonly_arrays():
    """测试数组只读约束。"""
    M = 8
    positions = np.random.randn(M, 3)

    array = ArrayDescriptor(
        type="test",
        params={},
        positions=positions,
    )

    # 应该无法修改
    with pytest.raises(ValueError):
        array.positions[0, 0] = 999.0
