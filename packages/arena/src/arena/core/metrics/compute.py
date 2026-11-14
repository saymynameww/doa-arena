"""指标计算函数。"""

from __future__ import annotations

import numpy as np
from arena_api import Estimate, kit


def match_and_compute(
    estimate: Estimate,
    truth: np.ndarray,
) -> dict[str, float | np.ndarray]:
    """匹配估计与真值，计算基础指标。

    Args:
        estimate: 估计结果
        truth: 真实角度，形状 (K,)

    Returns:
        指标字典，包含：
        - K_hat: 估计信源数
        - K: 真实信源数
        - matched_pairs: 匹配对，形状 (min(K, K̂), 2)
        - matched_errors: 匹配误差，形状 (min(K, K̂),)
        - rmse: RMSE（度）
        - max_error: 最大误差（度）
        - success: 是否成功（K̂ == K）
    """
    K = len(truth)
    K_hat = estimate.K_hat

    # 匹配
    matched_pairs, matched_errors = kit.hungarian_matching(
        estimate.angles,
        truth,
    )

    # RMSE
    if len(matched_errors) > 0:
        rmse = np.sqrt(np.mean(matched_errors**2))
        max_error = np.max(matched_errors)
    else:
        rmse = np.nan
        max_error = np.nan

    # 成功标志
    success = K_hat == K

    return {
        "K_hat": K_hat,
        "K": K,
        "matched_pairs": matched_pairs,
        "matched_errors": matched_errors,
        "rmse": rmse,
        "max_error": max_error,
        "success": success,
    }


def compute_metrics(
    estimates: list[Estimate],
    truth: np.ndarray,
) -> dict[str, float]:
    """批量计算指标统计量。

    Args:
        estimates: 估计结果列表
        truth: 真实角度

    Returns:
        统计指标字典：
        - rmse_mean: RMSE 均值
        - rmse_std: RMSE 标准差
        - success_rate: 成功率（正确检测信源数的比例）
        - avg_K_hat: 平均估计信源数
    """
    num_trials = len(estimates)
    K = len(truth)

    rmses = []
    successes = []
    K_hats = []

    for est in estimates:
        result = match_and_compute(est, truth)
        rmses.append(result["rmse"])
        successes.append(result["success"])
        K_hats.append(result["K_hat"])

    # 过滤 NaN
    rmses_valid = [r for r in rmses if not np.isnan(r)]

    if len(rmses_valid) > 0:
        rmse_mean = float(np.mean(rmses_valid))
        rmse_std = float(np.std(rmses_valid))
    else:
        rmse_mean = np.nan
        rmse_std = np.nan

    success_rate = float(np.mean(successes))
    avg_K_hat = float(np.mean(K_hats))

    return {
        "rmse_mean": rmse_mean,
        "rmse_std": rmse_std,
        "success_rate": success_rate,
        "avg_K_hat": avg_K_hat,
        "num_trials": num_trials,
        "num_valid": len(rmses_valid),
    }
