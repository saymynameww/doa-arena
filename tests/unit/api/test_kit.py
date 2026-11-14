"""测试 arena_api.kit 工具箱。"""

import numpy as np
import pytest
from arena_api import kit


def test_ula_steering():
    """测试 ULA 导向矢量。"""
    angles = np.array([-30, 0, 30])
    M = 8
    d = 0.5

    A = kit.ula_steering(angles, M, d)

    assert A.shape == (M, 3)
    assert A.dtype == np.complex128

    # 验证归一化
    for k in range(3):
        assert np.allclose(np.abs(A[:, k]).mean(), 1.0, atol=0.1)

    # 0° 应该是全 1
    assert np.allclose(A[:, 1], 1.0)


def test_subspace_decomposition():
    """测试子空间分解。"""
    M = 8
    K = 2

    # 构造简单的协方差矩阵
    # R = A·P·A^H + σ²I
    angles = np.array([-10, 10])
    A = kit.ula_steering(angles, M, d=0.5)
    P = np.diag([10.0, 10.0])  # 信号功率
    sigma2 = 1.0  # 噪声功率

    R = A @ P @ A.conj().T + sigma2 * np.eye(M)

    # 分解
    Us, Un, λs, λn = kit.subspace_decomposition(R, K)

    assert Us.shape == (M, K)
    assert Un.shape == (M, M - K)
    assert len(λs) == K
    assert len(λn) == M - K

    # 信号特征值应该远大于噪声特征值
    assert λs.min() > λn.max() * 2


def test_spatial_smoothing():
    """测试空间平滑。"""
    M = 16
    R = np.random.randn(M, M) + 1j * np.random.randn(M, M)
    R = R @ R.conj().T  # 确保 Hermitian

    L = 10

    # 前向平滑
    R_f = kit.spatial_smoothing(R, L, forward_backward=False)
    assert R_f.shape == (L, L)

    # 前后向平滑
    R_fb = kit.spatial_smoothing(R, L, forward_backward=True)
    assert R_fb.shape == (L, L)

    # 前后向应该更接近 Hermitian
    assert np.allclose(R_fb, R_fb.conj().T)


def test_music_spectrum():
    """测试 MUSIC 谱计算。"""
    M = 8
    K = 2

    # 简单场景
    angles_true = np.array([-10, 10])
    A_true = kit.ula_steering(angles_true, M, d=0.5)

    # 构造协方差
    P = np.diag([10.0, 10.0])
    sigma2 = 1.0
    R = A_true @ P @ A_true.conj().T + sigma2 * np.eye(M)

    # 子空间
    _, Un, _, _ = kit.subspace_decomposition(R, K)

    # 谱搜索
    grid = np.arange(-90, 90.1, 1.0)
    A_grid = kit.ula_steering(grid, M, d=0.5)
    spectrum = kit.music_spectrum(A_grid, Un)

    assert len(spectrum) == len(grid)
    assert np.all(spectrum > 0)

    # 峰值应该在真实角度附近
    peak_idx = np.argsort(spectrum)[-K:]
    peak_angles = grid[peak_idx]

    for angle_true in angles_true:
        assert np.any(np.abs(peak_angles - angle_true) < 2.0)


def test_peak_search():
    """测试峰值搜索。"""
    # 构造测试谱
    grid = np.arange(-90, 90.1, 1.0)
    spectrum = np.zeros_like(grid)

    # 添加两个峰
    spectrum[80] = 10.0  # -10°
    spectrum[100] = 8.0  # 10°
    spectrum[120] = 5.0  # 30°

    # 搜索前 2 峰
    peak_angles, peak_values = kit.peak_search(spectrum, grid, K=2)

    assert len(peak_angles) == 2
    assert -12 < peak_angles[0] < -8  # 第一峰在 -10° 附近
    assert 8 < peak_angles[1] < 12    # 第二峰在 10° 附近


def test_root_music():
    """测试 Root-MUSIC。"""
    M = 8
    K = 2

    # 构造协方差
    angles_true = np.array([-15, 20])
    A = kit.ula_steering(angles_true, M, d=0.5)
    P = np.diag([10.0, 10.0])
    sigma2 = 0.1
    R = A @ P @ A.conj().T + sigma2 * np.eye(M)

    # Root-MUSIC
    angles_est = kit.root_music(R, K, d=0.5)

    assert len(angles_est) == K

    # 估计应该接近真值
    for angle_true in angles_true:
        assert np.any(np.abs(angles_est - angle_true) < 3.0)


def test_esprit():
    """测试 ESPRIT。"""
    M = 8
    K = 2

    # 构造协方差
    angles_true = np.array([-20, 15])
    A = kit.ula_steering(angles_true, M, d=0.5)
    P = np.diag([10.0, 10.0])
    sigma2 = 0.1
    R = A @ P @ A.conj().T + sigma2 * np.eye(M)

    # LS-ESPRIT
    angles_ls = kit.esprit(R, K, d=0.5, method="ls")
    assert len(angles_ls) == K

    # TLS-ESPRIT
    angles_tls = kit.esprit(R, K, d=0.5, method="tls")
    assert len(angles_tls) == K

    # 都应该接近真值
    for angle_true in angles_true:
        assert np.any(np.abs(angles_ls - angle_true) < 3.0)
        assert np.any(np.abs(angles_tls - angle_true) < 3.0)


def test_hungarian_matching():
    """测试匈牙利匹配。"""
    estimates = np.array([-10.2, 5.3])
    truth = np.array([-10.0, 5.0])

    pairs, errors = kit.hungarian_matching(estimates, truth)

    assert pairs.shape == (2, 2)
    assert len(errors) == 2

    # 检查匹配正确性
    assert np.all(errors < 0.5)


def test_hungarian_matching_unequal():
    """测试不等数量的匹配。"""
    # K̂ > K
    estimates = np.array([-10, 0, 10])
    truth = np.array([-10, 10])

    pairs, errors = kit.hungarian_matching(estimates, truth)

    assert len(pairs) == 2  # min(3, 2)
    assert len(errors) == 2

    # K̂ < K
    estimates = np.array([-10])
    truth = np.array([-10, 10])

    pairs, errors = kit.hungarian_matching(estimates, truth)

    assert len(pairs) == 1  # min(1, 2)
    assert len(errors) == 1
