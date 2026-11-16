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
    angles = np.asarray(angles, dtype=float)
    K = len(angles)
    if N < 1 or noise_power <= 0:
        raise ValueError("快拍数和噪声功率必须大于零")
    A = array.steering(angles)
    if K >= array.M or np.linalg.matrix_rank(A) < K:
        return np.full(K, np.nan)
    powers = noise_power * 10 ** (np.broadcast_to(np.asarray(snr_db), (K,)) / 10)
    P = np.diag(powers) if signal_covariance is None else np.asarray(signal_covariance)
    D = array.steering_derivative(angles)
    R = A @ P @ A.conj().T + noise_power * np.eye(array.M)
    # 架构 5.7：随机信号完整 Fisher 信息矩阵，保留交叉项。
    projection = np.eye(array.M) - A @ np.linalg.pinv(A)
    information = np.real(
        (D.conj().T @ projection @ D) * (P @ A.conj().T @ np.linalg.solve(R, A) @ P).T
    )
    information = (information + information.T) / 2
    if np.linalg.matrix_rank(information) < K:
        return np.full(K, np.nan)
    covariance = noise_power / (2 * N) * np.linalg.inv(information)
    return np.diag(covariance) * (180 / np.pi) ** 2


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
