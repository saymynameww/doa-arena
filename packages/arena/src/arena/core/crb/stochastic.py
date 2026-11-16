"""随机信号 CRB 计算。

按架构文档 8.2 节实现。
"""

from __future__ import annotations

import numpy as np

from arena_api import ArrayDescriptor


def compute_stochastic_crb(
    array: ArrayDescriptor,
    angles: np.ndarray,
    snr_db: float | np.ndarray,
    N: int,
    signal_covariance: np.ndarray | None = None,
    noise_power: float = 1.0,
) -> np.ndarray:
    """计算随机信号 CRB。

    Args:
        array: 阵列描述
        angles: 真实角度，形状 (K,)
        snr_db: SNR（dB），标量或形状 (K,)
        N: 快拍数
        signal_covariance: 信号协方差 P，形状 (K, K)；None 表示不相干
        noise_power: 噪声功率

    Returns:
        CRB，形状 (K,)，单位度²
    """
    K = len(angles)
    M = array.M

    # SNR 转功率
    if isinstance(snr_db, (int, float)):
        snr_db = np.full(K, snr_db)
    else:
        snr_db = np.asarray(snr_db)

    signal_powers = noise_power * (10 ** (snr_db / 10))

    # 信号协方差
    if signal_covariance is None:
        P = np.diag(signal_powers)
    else:
        P = signal_covariance

    # 导向矢量和导数
    A = array.steering(angles)  # (M, K)
    D = array.steering_derivative(angles)  # (M, K)，每弧度

    # 转换为每度
    D = D * (np.pi / 180)  # 度到弧度的转换因子

    # 协方差矩阵 R = A·P·A^H + σ²I
    R = A @ P @ A.conj().T + noise_power * np.eye(M)

    # R 逆
    try:
        R_inv = np.linalg.inv(R)
    except np.linalg.LinAlgError:
        # 奇异，返回无穷
        return np.full(K, np.inf)

    # Fisher 信息矩阵（简化公式，不相干情况）
    # FIM_kk = 2N·Re{tr[(∂A/∂θ_k)^H · Π_A⊥ · (∂A/∂θ_k) · P_kk]}
    # 其中 Π_A⊥ = I - A·(A^H·R^{-1}·A)^{-1}·A^H·R^{-1}

    # 计算投影矩阵（使用 Slepian-Bangs 公式的简化形式）
    # FIM = 2N·Re{D^H · Π · D ⊙ P}
    # 这里使用对角近似（不相干信号）

    crb = np.zeros(K)

    for k in range(K):
        # 第 k 个信源的导数
        d_k = D[:, k : k + 1]  # (M, 1)

        # 简化公式（不相干信号）：
        # CRB_k ≈ σ²/(2N·σ_k²·d_k^H·(I - A·A^H)·d_k)
        # 更精确的版本：
        # CRB_k = 1/(2N·Re{d_k^H·R^{-1}·d_k·P_kk - d_k^H·R^{-1}·A·P·A^H·R^{-1}·d_k})

        # 使用 Slepian-Bangs 公式
        term1 = (d_k.conj().T @ R_inv @ d_k).real[0, 0]
        term2 = (d_k.conj().T @ R_inv @ A @ P @ A.conj().T @ R_inv @ d_k).real[0, 0]

        fisher_kk = 2 * N * (term1 * P[k, k] - term2)

        if fisher_kk > 0:
            crb[k] = 1.0 / fisher_kk
        else:
            crb[k] = np.inf

    # 转换为度²（已经是度的单位）
    return crb


def compute_crb_batch(
    array: ArrayDescriptor,
    angles: np.ndarray,
    snr_db_list: list[float],
    N: int,
) -> dict[float, np.ndarray]:
    """批量计算不同 SNR 下的 CRB。

    Args:
        array: 阵列描述
        angles: 真实角度
        snr_db_list: SNR 列表
        N: 快拍数

    Returns:
        字典，键为 SNR，值为 CRB 数组
    """
    results = {}

    for snr_db in snr_db_list:
        crb = compute_stochastic_crb(
            array=array,
            angles=angles,
            snr_db=snr_db,
            N=N,
        )
        results[snr_db] = crb

    return results
