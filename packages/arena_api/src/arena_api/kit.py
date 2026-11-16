"""算法工具箱（只依赖 NumPy）。

提供常用的信号处理和子空间方法函数，供内置算法和外部算法使用。
"""

from __future__ import annotations

import numpy as np

# ============================================================================
# 协方差与空间平滑
# ============================================================================


def spatial_smoothing(
    R: np.ndarray,
    L: int,
    forward_backward: bool = False,
) -> np.ndarray:
    """空间平滑。

    Args:
        R: 样本协方差矩阵，形状 (M, M)
        L: 子阵阵元数，要求 K < L <= M
        forward_backward: 是否使用前后向平滑

    Returns:
        平滑后的协方差矩阵，形状 (L, L)

    Raises:
        ValueError: L 不在合法范围内
    """
    M = R.shape[0]
    if not (2 <= L <= M):
        raise ValueError(f"子阵阵元数 L 必须在 [2, {M}] 范围内，实际为 {L}")

    # 前向平滑
    P = M - L + 1  # 子阵数
    R_f = np.zeros((L, L), dtype=complex)
    for i in range(P):
        R_sub = R[i : i + L, i : i + L]
        R_f += R_sub
    R_f /= P

    if not forward_backward:
        return R_f

    # 后向平滑
    # 交换矩阵
    J = np.eye(L)[::-1]
    R_b = J @ R_f.conj() @ J
    R_fb = (R_f + R_b) / 2

    return R_fb


def forward_backward_averaging(R: np.ndarray) -> np.ndarray:
    """前后向平均（不做空间平滑）。

    Args:
        R: 协方差矩阵，形状 (M, M)

    Returns:
        平均后的协方差矩阵，形状 (M, M)
    """
    M = R.shape[0]
    J = np.eye(M)[::-1]
    R_b = J @ R.conj() @ J
    return (R + R_b) / 2


# ============================================================================
# 子空间分解
# ============================================================================


def subspace_decomposition(
    R: np.ndarray,
    K: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """子空间分解（特征分解）。

    Args:
        R: 协方差矩阵，形状 (M, M)
        K: 信号子空间维数（信源数）

    Returns:
        (Us, Un, λs, λn)
        - Us: 信号子空间，形状 (M, K)
        - Un: 噪声子空间，形状 (M, M-K)
        - λs: 信号特征值，形状 (K,)，降序
        - λn: 噪声特征值，形状 (M-K,)，降序
    """
    M = R.shape[0]
    if K >= M:
        raise ValueError(f"信源数 K={K} 必须小于阵元数 M={M}")

    # 特征分解
    eigvals, eigvecs = np.linalg.eigh(R)

    # 降序排列
    idx = np.argsort(eigvals)[::-1]
    eigvals = eigvals[idx]
    eigvecs = eigvecs[:, idx]

    # 分割
    Us = eigvecs[:, :K]
    Un = eigvecs[:, K:]
    λs = eigvals[:K]
    λn = eigvals[K:]

    return Us, Un, λs, λn


# ============================================================================
# 导向矢量
# ============================================================================


def ula_steering(
    angles: np.ndarray,
    M: int,
    d: float = 0.5,
) -> np.ndarray:
    """ULA 导向矢量。

    Args:
        angles: 角度（度），形状 (K,)
        M: 阵元数
        d: 阵元间距（单位 λ）

    Returns:
        导向矢量矩阵，形状 (M, K)
    """
    angles = np.asarray(angles, dtype=np.float64)
    theta_rad = np.deg2rad(angles)

    # 阵元位置：[0, d, 2d, ..., (M-1)d]
    m = np.arange(M)

    # 相位：-2π·m·d·sin(θ)
    phase = -2.0 * np.pi * np.outer(m * d, np.sin(theta_rad))
    a = np.exp(1j * phase)

    return a


def ula_steering_derivative(
    angles: np.ndarray,
    M: int,
    d: float = 0.5,
) -> np.ndarray:
    """ULA 导向矢量对角度的导数（每弧度）。

    Args:
        angles: 角度（度），形状 (K,)
        M: 阵元数
        d: 阵元间距（单位 λ）

    Returns:
        导数矩阵，形状 (M, K)
    """
    angles = np.asarray(angles, dtype=np.float64)
    theta_rad = np.deg2rad(angles)

    m = np.arange(M)
    a = ula_steering(angles, M, d)

    # da/dθ = -j·2π·m·d·cos(θ)·a(θ)
    da_dtheta = -1j * 2.0 * np.pi * np.outer(m * d, np.cos(theta_rad)) * a

    return da_dtheta


# ============================================================================
# 谱峰搜索
# ============================================================================


def peak_search(
    spectrum: np.ndarray,
    grid: np.ndarray,
    K: int,
    min_separation: float | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """谱峰搜索（取前 K 峰）。

    Args:
        spectrum: 谱值，形状 (G,)
        grid: 角度网格（度），形状 (G,)
        K: 需要的峰数
        min_separation: 最小峰间隔（度），None 表示不限制

    Returns:
        (peak_angles, peak_values)
        - peak_angles: 峰值角度，形状 (K',)，K' <= K
        - peak_values: 峰值大小，形状 (K',)
    """
    if K <= 0:
        return np.array([]), np.array([])

    # 找所有局部最大值
    is_peak = np.zeros(len(spectrum), dtype=bool)
    for i in range(1, len(spectrum) - 1):
        if spectrum[i] > spectrum[i - 1] and spectrum[i] > spectrum[i + 1]:
            is_peak[i] = True

    # 按峰值大小排序
    peak_indices = np.where(is_peak)[0]
    peak_values = spectrum[peak_indices]
    sorted_idx = np.argsort(peak_values)[::-1]

    peak_indices = peak_indices[sorted_idx]
    peak_values = peak_values[sorted_idx]
    peak_angles = grid[peak_indices]

    # 应用最小间隔约束
    if min_separation is not None:
        selected: list[int] = []
        for i, (angle, value) in enumerate(zip(peak_angles, peak_values)):
            # 检查与已选峰的间隔
            too_close = False
            for sel_angle in selected:
                if abs(angle - sel_angle) < min_separation:
                    too_close = True
                    break
            if not too_close:
                selected.append(angle)
            if len(selected) >= K:
                break
        peak_angles = np.array(selected)
        peak_values = spectrum[np.searchsorted(grid, peak_angles)]
    else:
        # 直接取前 K 个
        peak_angles = peak_angles[:K]
        peak_values = peak_values[:K]

    return peak_angles, peak_values


# ============================================================================
# MUSIC 与 Root-MUSIC
# ============================================================================


def music_spectrum(
    A: np.ndarray,
    Un: np.ndarray,
) -> np.ndarray:
    """MUSIC 伪谱。

    Args:
        A: 导向矢量矩阵，形状 (M, G)
        Un: 噪声子空间，形状 (M, M-K)

    Returns:
        谱值，形状 (G,)
    """
    denominator = np.sum(np.abs(Un.conj().T @ A) ** 2, axis=0)
    return 1 / np.maximum(denominator, np.finfo(float).tiny)


def root_music(
    R: np.ndarray,
    K: int,
    d: float = 0.5,
) -> np.ndarray:
    """Root-MUSIC 算法（仅适用于 ULA）。

    Args:
        R: 协方差矩阵，形状 (M, M)
        K: 信源数
        d: 阵元间距（单位 λ）

    Returns:
        估计角度（度），形状 (K,)
    """
    M = R.shape[0]

    # 噪声子空间
    _, Un, _, _ = subspace_decomposition(R, K)

    # 构造多项式：C(z) = e^H · Un · Un^H · e
    # 其中 e = [1, z, z^2, ..., z^(M-1)]^T
    # 等价于对 Un·Un^H 的每条对角线求和
    UnUnH = Un @ Un.conj().T

    # 多项式系数（Toeplitz 结构）
    c = np.zeros(2 * M - 1, dtype=complex)
    for k in range(-(M - 1), M):
        # 第 k 条对角线
        if k >= 0:
            c[M - 1 + k] = np.trace(UnUnH, offset=k)
        else:
            c[M - 1 + k] = np.trace(UnUnH, offset=k)

    # 求根
    roots = np.roots(c[::-1])

    # 选择单位圆上的根（最接近单位圆的 K 个）
    abs_roots = np.abs(roots)
    inside_unit_circle = abs_roots < 1.0

    # 取圆内且最接近单位圆的 K 个根
    roots_inside = roots[inside_unit_circle]
    distances = 1.0 - np.abs(roots_inside)
    sorted_idx = np.argsort(distances)

    selected_roots = roots_inside[sorted_idx[:K]]

    # 根到角度：z = exp(j·2π·d·sin(θ))
    # sin(θ) = angle(z) / (2π·d)
    angles_rad = -np.angle(selected_roots) / (2.0 * np.pi * d)
    angles_rad = angles_rad[np.abs(angles_rad) <= 1]
    angles_deg = np.rad2deg(np.arcsin(angles_rad))

    return np.sort(angles_deg)


# ============================================================================
# ESPRIT
# ============================================================================


def esprit(
    R: np.ndarray,
    K: int,
    d: float = 0.5,
    method: str = "tls",
) -> np.ndarray:
    """ESPRIT 算法（仅适用于 ULA）。

    Args:
        R: 协方差矩阵，形状 (M, M)
        K: 信源数
        d: 阵元间距（单位 λ）
        method: "ls" 或 "tls"

    Returns:
        估计角度（度），形状 (K,)
    """
    # 信号子空间
    Us, _, _, _ = subspace_decomposition(R, K)

    # 子阵选择：前 M-1 个和后 M-1 个
    Us1 = Us[:-1, :]  # (M-1, K)
    Us2 = Us[1:, :]  # (M-1, K)

    if method == "ls":
        # LS-ESPRIT：Φ = (Us1^H · Us1)^{-1} · Us1^H · Us2
        Phi = np.linalg.lstsq(Us1, Us2, rcond=None)[0]
    elif method == "tls":
        # TLS-ESPRIT：对 [Us1, Us2] 做 SVD
        C = np.hstack([Us1, Us2])  # (M-1, 2K)
        _, _, Vh = np.linalg.svd(C, full_matrices=True)
        V = Vh.conj().T

        # 分块
        V12 = V[:K, K:]  # (K, K)
        V22 = V[K:, K:]  # (K, K)

        # Φ = -V12 · V22^{-1}
        Phi = -V12 @ np.linalg.inv(V22)
    else:
        raise ValueError(f"未知方法：{method}，必须是 'ls' 或 'tls'")

    # 特征值到角度
    eigvals = np.linalg.eigvals(Phi)

    # ULA 导向矢量使用 -2π·d·sin(θ) 相位，因此特征值相位取负号还原角度。
    angles_rad = -np.angle(eigvals) / (2.0 * np.pi * d)
    angles_rad = angles_rad[np.abs(angles_rad) <= 1]
    angles_deg = np.rad2deg(np.arcsin(angles_rad))

    return np.sort(angles_deg)


# ============================================================================
# 匈牙利匹配
# ============================================================================


def hungarian_matching(
    estimates: np.ndarray,
    truth: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """匈牙利算法匹配估计与真值。

    Args:
        estimates: 估计角度，形状 (K̂,)
        truth: 真实角度，形状 (K,)

    Returns:
        (matched_pairs, matched_errors)
        - matched_pairs: 形状 (min(K, K̂), 2)，每行 [est_idx, truth_idx]
        - matched_errors: 形状 (min(K, K̂),)
    """
    from scipy.optimize import linear_sum_assignment

    K_hat = len(estimates)
    K = len(truth)

    if K_hat == 0 or K == 0:
        return np.empty((0, 2), dtype=int), np.empty(0)

    # 代价矩阵：|θ̂ - θ|
    cost = np.abs(estimates[:, None] - truth[None, :])

    # 匈牙利算法
    row_ind, col_ind = linear_sum_assignment(cost)

    matched_pairs = np.column_stack([row_ind, col_ind])
    matched_errors = cost[row_ind, col_ind]

    return matched_pairs, matched_errors


def auto_subarray(M: int, K: int, fb: bool = False) -> int:
    """接口规范 13.2：在可分辨条件下使用最大子阵孔径。"""
    return M - ((K + 1) // 2 if fb else K) + 1


def checked_subarray(M: int, K: int, mode: str, requested: int | None) -> int:
    """校验平滑子阵，不静默夹断用户配置。"""
    L = requested if requested is not None else auto_subarray(M, K, mode == "fb")
    needed = (K + 1) // 2 if mode == "fb" else K
    if not K < L <= M or M - L + 1 < needed:
        raise ValueError(f"子阵阵元数 {L}、子阵数 {M - L + 1} 无法分辨 {K} 个信源，请调整子阵大小")
    return L


def refine_peaks(spectrum: np.ndarray, grid: np.ndarray, angles: np.ndarray) -> np.ndarray:
    """对局部谱峰作三点抛物线细化，端点不参与。"""
    refined = []
    for angle in angles:
        i = int(np.argmin(np.abs(grid - angle)))
        if 0 < i < len(grid) - 1:
            left, mid, right = spectrum[i - 1 : i + 2]
            denominator = left - 2 * mid + right
            offset = 0.5 * (left - right) / denominator if denominator else 0
            angle = grid[i] + float(np.clip(offset, -0.5, 0.5)) * (grid[i + 1] - grid[i])
        refined.append(angle)
    return np.sort(np.asarray(refined))
